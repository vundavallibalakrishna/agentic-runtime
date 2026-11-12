"""Where research looks: the tenant's own documents, and the web when it is configured.

Web search is the provider the tenant set for ``general.search`` (``tools/searching.py``).
There is one web search in the product. With no provider set, research searches the
document library alone and says so. It never answers from a built-in page.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

import httpx

from ar_domain.tools.searching import SearchRejectedError, SearchUnavailableError, provider_for

if TYPE_CHECKING:
    from typing import Any

LIBRARY = "library://"
_WORD = re.compile(r"[^\W_]+")
_STEM = 5
_LONG = 4
_ENOUGH = 8
# The lowest cosine at which a library passage counts as about the question, when a real
# embedding model ranks it. The tenant may raise or lower it with ``research.minScore``.
_DEFAULT_MIN_SCORE = 0.3
# A tenant library larger than this is not embedded on every query. Word matching still
# finds its passages, and the production path is embeddings stored at ingest (OQ-130).
_MAX_EMBED = 400


def search(store: Any, tenant_id: object, query: str, *, limit: int = 4) -> list[dict[str, str]]:
    """Library passages first, then web results. Both are real or absent."""
    count = max(1, limit)
    found = library_hits(store, tenant_id, query, limit=count)
    seen = {row["url"] for row in found}
    for row in web_hits(store, tenant_id, query, limit=count):
        if row["url"] not in seen:
            found.append(row)
            seen.add(row["url"])
    return found


def web_configured(store: Any, tenant_id: object) -> bool:
    try:
        provider_for(store, tenant_id)
    except SearchUnavailableError:
        return False
    return True


def web_hits(store: Any, tenant_id: object, query: str, *, limit: int) -> list[dict[str, str]]:
    """Results from the tenant's web search provider. None is configured: no results."""
    try:
        rows = provider_for(store, tenant_id).search(query, limit=limit)
    except SearchUnavailableError, SearchRejectedError, httpx.HTTPError:
        return []
    return [
        {
            "url": str(row.get("url") or ""),
            "title": str(row.get("title") or row.get("url") or ""),
            "snippet": str(row.get("snippet") or ""),
        }
        for row in rows
        if isinstance(row, dict) and row.get("url")
    ]


def library_hits(store: Any, tenant_id: object, query: str, *, limit: int) -> list[dict[str, str]]:
    """The tenant's library passages that answer the query, one address per passage.

    Two signals, joined. **By meaning**: when the tenant has an embedding model on the
    ``embed`` alias, each passage is scored by the cosine of its vector with the query's,
    and those above ``research.minScore`` (default 0.3) are kept, best first. This finds a
    passage worded differently from the question. **By words**: the share of distinctive
    query words a passage holds (``research.minMatchedWords``, default 1), which finds a
    passage an embedding model might rank low and never regresses the old behaviour. The
    two lists are merged, meaning first, one address per passage, up to ``limit``.

    With no embedding model the result is the word match alone. A fake model's vectors
    carry no meaning, so only an exact-text passage clears the bar and the word match
    still does the work.
    """
    if not isinstance(tenant_id, uuid.UUID):
        return []
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in (
        *_semantic_hits(store, tenant_id, query, limit=limit),
        *_lexical_hits(store, tenant_id, query, limit=limit),
    ):
        url = row["url"]
        if url in seen:
            continue
        seen.add(url)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged


def _lexical_hits(
    store: Any, tenant_id: uuid.UUID, query: str, *, limit: int
) -> list[dict[str, str]]:
    """Passages that share distinctive words with the query (the word signal)."""
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415

    reader = Actor(tenant_id=tenant_id, user_id=tenant_id, permissions=frozenset())
    distinctive = _distinctive(store, tenant_id, query)
    needed = _needed(store, tenant_id)
    rows: list[dict[str, str]] = []
    for hit in DocumentLibrary(store).search(reader, query):
        anchor = str(hit.get("anchor") or "")
        address = f"{LIBRARY}{hit.get('document_id')}#{anchor}"
        have = _words(library_page(store, tenant_id, address) or "")
        if sum(1 for word in distinctive if _holds(word, have)) < needed:
            continue
        title = str(hit.get("title") or "Document")
        rows.append(
            {
                "url": address,
                "title": f"{title} ({anchor})" if anchor else title,
                "snippet": str(hit.get("snippet") or ""),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _semantic_hits(
    store: Any, tenant_id: uuid.UUID, query: str, *, limit: int
) -> list[dict[str, str]]:
    """Passages closest to the query in meaning, best first (the embedding signal).

    Empty when the tenant has no embedding model, when the model does not answer, or when
    the library is larger than ``_MAX_EMBED`` (word matching still covers it).
    """
    from ar_domain.models.embedding import (  # noqa: PLC0415
        EmbeddingFailedError,
        EmbeddingUnconfiguredError,
        embed,
        embedding_model,
    )

    passages = _library_passages(store, tenant_id)
    if not passages or len(passages) > _MAX_EMBED:
        return []
    try:
        target = embedding_model(store, tenant_id)
        vectors = embed(target, [query, *(row["text"] for row in passages)])
    except EmbeddingUnconfiguredError, EmbeddingFailedError:
        return []
    if len(vectors) != len(passages) + 1:
        return []
    ranked = rank_by_similarity(
        vectors[0], vectors[1:], min_score=_min_score(store, tenant_id), limit=limit
    )
    rows: list[dict[str, str]] = []
    for index, _score in ranked:
        passage = passages[index]
        anchor = passage["anchor"]
        title = passage["title"]
        rows.append(
            {
                "url": f"{LIBRARY}{passage['document_id']}#{anchor}",
                "title": f"{title} ({anchor})" if anchor else title,
                "snippet": passage["text"][:200],
            }
        )
    return rows


def rank_by_similarity(
    query_vec: list[float], passage_vecs: list[list[float]], *, min_score: float, limit: int
) -> list[tuple[int, float]]:
    """Passage indexes whose vector clears ``min_score``, highest cosine first.

    Pure: the caller supplies the vectors, so the ranking is tested without a model.
    """
    from ar_domain.memory.logic import cosine  # noqa: PLC0415

    scored = [(index, cosine(query_vec, vector)) for index, vector in enumerate(passage_vecs)]
    kept = [pair for pair in scored if pair[1] >= min_score]
    kept.sort(key=lambda pair: pair[1], reverse=True)
    return kept[: max(1, limit)]


def _library_passages(store: Any, tenant_id: uuid.UUID) -> list[dict[str, str]]:
    """Every library passage of the tenant, as ``document_id``/``anchor``/``title``/``text``."""
    passages: list[dict[str, str]] = []
    for document_id, row in getattr(store, "library_documents", {}).items():
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            continue
        title = str(row.get("title") or "Document")
        listed = row.get("passages")
        for passage in listed if isinstance(listed, list) else []:
            if not isinstance(passage, dict):
                continue
            text = str(passage.get("text") or "")
            if not text:
                continue
            passages.append(
                {
                    "document_id": str(document_id),
                    "anchor": str(passage.get("anchor") or ""),
                    "title": title,
                    "text": text,
                }
            )
    return passages


def _min_score(store: Any, tenant_id: object) -> float:
    settings = getattr(store, "tenant_settings", {}).get(tenant_id)
    research = settings.get("research") if isinstance(settings, dict) else None
    raw = None
    if isinstance(research, dict):
        raw = research.get("min_score", research.get("minScore"))
    if isinstance(raw, int | float) and not isinstance(raw, bool) and 0.0 <= float(raw) <= 1.0:
        return float(raw)
    return _DEFAULT_MIN_SCORE


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _holds(word: str, have: set[str]) -> bool:
    """The passage has the word, or one with the same first letters (approves, approved)."""
    if word in have:
        return True
    return any(other.startswith(word[:_STEM]) for other in have if len(other) >= _STEM)


def _distinctive(store: Any, tenant_id: uuid.UUID, query: str) -> set[str]:
    """The query's longer words, without those most of the tenant's passages hold.

    A library of a few passages is all about one subject, so its common words are the
    subject. The "most passages" rule applies from ``_ENOUGH`` passages up.
    """
    passages: list[set[str]] = []
    for row in getattr(store, "library_documents", {}).values():
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            continue
        listed = row.get("passages")
        passages.extend(
            _words(str(passage.get("text") or ""))
            for passage in (listed if isinstance(listed, list) else [])
            if isinstance(passage, dict)
        )
    longer = {word for word in _words(query) if len(word) >= _LONG}
    if len(passages) < _ENOUGH:
        return longer
    most = len(passages) // 2
    return {word for word in longer if sum(1 for have in passages if _holds(word, have)) <= most}


def _needed(store: Any, tenant_id: object) -> int:
    settings = getattr(store, "tenant_settings", {}).get(tenant_id)
    research = settings.get("research") if isinstance(settings, dict) else None
    raw = None
    if isinstance(research, dict):
        raw = research.get("min_matched_words", research.get("minMatchedWords"))
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw
    return 1


def library_page(store: Any, tenant_id: object, url: str) -> str | None:
    """The text of one library passage, or None when this tenant has no such passage."""
    if not url.startswith(LIBRARY) or not isinstance(tenant_id, uuid.UUID):
        return None
    document, _mark, anchor = url[len(LIBRARY) :].partition("#")
    try:
        document_id = uuid.UUID(document)
    except ValueError:
        return None
    row = getattr(store, "library_documents", {}).get(document_id)
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        return None
    passages = row.get("passages")
    for passage in passages if isinstance(passages, list) else []:
        if isinstance(passage, dict) and str(passage.get("anchor") or "") == anchor:
            return str(passage.get("text") or "")
    return None


def scope(store: Any, tenant_id: object) -> str:
    """What research searched, in words a person can act on."""
    documents = sum(
        1
        for row in getattr(store, "library_documents", {}).values()
        if isinstance(row, dict) and row.get("tenant_id") == tenant_id
    )
    library = f"the document library ({documents} documents)"
    if web_configured(store, tenant_id):
        return f"Research searched {library} and the web."
    return (
        f"Research searched {library}. Web search is not configured: an administrator sets "
        "a search provider and its key to add the web."
    )

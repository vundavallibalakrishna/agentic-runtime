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

    The library scores a passage by the share of query words it holds, so "is", "the" and
    "of" alone make a match. Research needs the passage to be about the question, so it
    must share distinctive words with it: words of four letters or more, without those
    most of the tenant's passages hold. How many is the tenant's
    ``research.minMatchedWords`` (default 1; 0 keeps every library match). The match is by
    words, not meaning.
    """
    if not isinstance(tenant_id, uuid.UUID):
        return []
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

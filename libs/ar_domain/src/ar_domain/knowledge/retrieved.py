"""The passages a search returned, without their text.

Stored on the tool call and read by evals. The passage text stays in the
prompt and the citation, not in this record.
"""

from __future__ import annotations

from urllib.parse import urlparse


def retrieval_record(query: str, structured: object) -> dict[str, object] | None:
    """Ids, scores, the query and the rank. None when the call retrieved nothing."""
    hits = structured.get("hits") if isinstance(structured, dict) else None
    if not isinstance(hits, list) or not hits:
        return None
    passages: list[dict[str, object]] = []
    for rank, hit in enumerate(hits, start=1):
        if not isinstance(hit, dict):
            continue
        passages.append(
            {
                "chunk_id": str(hit.get("chunk_id") or hit.get("chunkId") or ""),
                "document_id": str(hit.get("document_id") or hit.get("documentId") or ""),
                "uri": str(hit.get("uri") or hit.get("url") or ""),
                "title": str(hit.get("title") or ""),
                "score": hit.get("rerank_score", hit.get("score")),
                "rank": rank,
            }
        )
    if not passages:
        return None
    asked = query
    if isinstance(structured, dict) and structured.get("query"):
        asked = str(structured.get("query"))
    return {"query": asked[:500], "passages": passages}


def page_keys(value: str) -> set[str]:
    """Identities of one page: the text itself, and the path when it is a URL."""
    raw = value.strip().casefold().rstrip("/")
    if not raw:
        return set()
    keys = {raw}
    if "://" in raw:
        path = urlparse(raw).path.casefold().rstrip("/")
        if path:
            keys.add(path)
    return keys


def retrieval_recall(
    expected: list[str], passages: list[dict[str, object]]
) -> tuple[float, int, int] | None:
    """Share of expected pages that were retrieved. None when the case names none."""
    wanted = [page_keys(item) for item in expected if item.strip()]
    wanted = [keys for keys in wanted if keys]
    if not wanted:
        return None
    have: set[str] = set()
    for row in passages:
        for field in ("document_id", "chunk_id", "uri", "title"):
            have.update(page_keys(str(row.get(field) or "")))
    found = sum(1 for keys in wanted if keys & have)
    return found / len(wanted), found, len(wanted)

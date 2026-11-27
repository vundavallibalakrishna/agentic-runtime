"""What a passage is embedded and searched as.

The stored passage text stays the passage itself. The indexed text leads with the
document title and the heading path, so a section is found with the page it belongs
to. ``INDEX_TEXT_VERSION`` changes when that text changes. A collection indexed at an
older version is rebuilt by the existing re-index workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Bump when the embedded or lexical text of a passage changes shape.
INDEX_TEXT_VERSION = 3


def passage_context(title: str, heading_path: list[str]) -> str:
    """Title, then the heading path, without repeating a heading that is the title."""
    parts: list[str] = []
    seen: set[str] = set()
    for part in [title, *heading_path]:
        text = part.strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        parts.append(text)
    return " / ".join(parts)


def indexed_text(title: str, heading_path: list[str], text: str) -> str:
    """The text that is embedded and indexed. The stored passage is ``text`` alone."""
    crumb = passage_context(title, heading_path)
    body = text.strip()
    if crumb and body:
        return f"{crumb}\n{body}"
    return crumb or body


def text_version(collection: dict[str, object]) -> int:
    """The index-text version a collection was last built with. Missing is 1."""
    chunking = collection.get("chunking")
    if not isinstance(chunking, dict):
        return 1
    raw = chunking.get("index_text_version", chunking.get("indexTextVersion"))
    if isinstance(raw, bool) or not isinstance(raw, int):
        return 1
    return raw


def chunking_with_text_version(chunking: dict[str, object]) -> dict[str, object]:
    """``chunking`` stamped with the index-text version this process writes."""
    stamped = dict(chunking)
    stamped["index_text_version"] = INDEX_TEXT_VERSION
    return stamped


async def queue_stale_reindex(store: Any, collections: list[dict[str, object]]) -> None:
    """Ask the ingest worker to rebuild a collection whose passages use an older text.

    With no workflow engine there is nothing to ask, and the search still uses the
    version in place. A re-index that is already queued is left as it is.
    """
    client = getattr(store, "temporal_client", None)
    if client is None or not hasattr(client, "start_workflow"):
        return
    from ar_common.errors import ArError  # noqa: PLC0415
    from ar_domain.knowledge.dispatch import request_reindex  # noqa: PLC0415
    from ar_domain.knowledge.reindexing import open_reindex  # noqa: PLC0415

    for collection in collections:
        if text_version(collection) >= INDEX_TEXT_VERSION:
            continue
        if open_reindex(store, collection.get("id")) is not None:
            continue
        chunking = collection.get("chunking")
        current = dict(chunking) if isinstance(chunking, dict) else {}
        target = {
            "embedding_alias": collection.get("embedding_alias"),
            "embedding_model": collection.get("embedding_model"),
            "embedding_model_id": (
                None
                if collection.get("embedding_model_id") is None
                else str(collection.get("embedding_model_id"))
            ),
            "store_collection": collection.get("store_collection"),
            "text_search_config": collection.get("text_search_config") or "simple",
            "chunking": chunking_with_text_version(current),
        }
        try:
            await request_reindex(store, collection, target, actor_id=None)
        except ArError:
            continue

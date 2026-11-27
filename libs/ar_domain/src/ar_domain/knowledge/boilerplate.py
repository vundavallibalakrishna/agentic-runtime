"""Drop blocks that repeat across a collection.

A paragraph whose normalised text appears in a configurable share of the
collection's documents is navigation, a footer or a banner. It is left out of
the passages. The count of what was dropped is kept on the document. Nothing
here names a site or a selector: repetition across the collection is the signal.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_SPLIT = re.compile(r"\n\s*\n")


def normalize_block(text: str) -> str:
    """Case and whitespace folded. The words stay in order."""
    return " ".join(text.split()).casefold()


def paragraph_blocks(text: str) -> list[str]:
    """Blank-line-separated blocks, headings included when they stand alone."""
    return [part.strip() for part in _SPLIT.split(text) if part.strip()]


def repeated_keys(documents: list[list[str]], *, share: float, min_chars: int) -> set[str]:
    """Normalised blocks present in at least ``share`` of the documents.

    A block shorter than ``min_chars`` is never repeated boilerplate. Fewer than
    two documents, or a share of 0, drops nothing.
    """
    count = len(documents)
    if share <= 0 or count < 2:
        return set()
    need = max(2, math.ceil(share * count))
    found: dict[str, int] = {}
    floor = max(min_chars, 1)
    for blocks in documents:
        seen: set[str] = set()
        for block in blocks:
            key = normalize_block(block)
            if len(key) < floor or key in seen:
                continue
            seen.add(key)
            found[key] = found.get(key, 0) + 1
    return {key for key, times in found.items() if times >= need}


def without_repeated(text: str, repeated: set[str], *, min_chars: int) -> tuple[str, int]:
    """``text`` with repeated blocks removed, and how many were removed."""
    if not repeated or not text.strip():
        return text, 0
    floor = max(min_chars, 1)
    kept: list[str] = []
    dropped = 0
    for part in _SPLIT.split(text):
        stripped = part.strip()
        key = normalize_block(stripped)
        if stripped and len(key) >= floor and key in repeated:
            dropped += 1
            continue
        if stripped:
            kept.append(stripped)
    return "\n\n".join(kept), dropped


def block_settings(collection: dict[str, object]) -> tuple[float, int]:
    """The collection's threshold, or the install default."""
    from ar_common.settings import get_settings  # noqa: PLC0415

    settings = get_settings()
    chunking = collection.get("chunking")
    raw = chunking if isinstance(chunking, dict) else {}
    share = raw.get("repeated_block_share", raw.get("repeatedBlockShare"))
    if isinstance(share, bool) or not isinstance(share, int | float):
        share = settings.knowledge_repeated_block_share
    chars = raw.get("repeated_block_min_chars", raw.get("repeatedBlockMinChars"))
    if isinstance(chars, bool) or not isinstance(chars, int):
        chars = settings.knowledge_repeated_block_min_chars
    return max(0.0, min(float(share), 1.0)), max(1, int(chars))


def repeated_in_collection(store: Any, collection: dict[str, object]) -> set[str]:
    """Blocks that already repeat across the version of the collection in use."""
    share, min_chars = block_settings(collection)
    if share <= 0:
        return set()
    version = int(collection.get("index_version") or 1)
    collection_id = collection.get("id")
    documents = getattr(store, "knowledge_documents", {})
    in_collection = {
        row.get("id")
        for row in documents.values()
        if isinstance(row, dict)
        and row.get("collection_id") == collection_id
        and row.get("status") != "deleted"
    }
    by_document: dict[object, list[str]] = {}
    chunks = getattr(store, "document_chunks", {})
    for row in chunks.values():
        if not isinstance(row, dict):
            continue
        if row.get("document_id") not in in_collection:
            continue
        if int(row.get("index_version") or 1) != version:
            continue
        text = str(row.get("text") or "").strip()
        if text:
            by_document.setdefault(row.get("document_id"), []).append(text)
    documents_blocks = [paragraph_blocks("\n\n".join(parts)) for parts in by_document.values()]
    return repeated_keys(documents_blocks, share=share, min_chars=min_chars)

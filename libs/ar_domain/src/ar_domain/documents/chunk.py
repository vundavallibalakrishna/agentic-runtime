"""Chunk passages and retrieve a window that fits a model context.

A long file stays on disk as passages. A question receives only the passages
that share its words, up to ``RETRIEVAL_BUDGET`` characters, with the page and
anchor kept on every piece.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ar_domain.documents.extract import Passage

TARGET_CHARS = 1000
OVERLAP = 120
RETRIEVAL_BUDGET = 12_000
_TOKEN = re.compile(r"[a-z0-9]{3,}")


def split_passage(passages: list[Passage]) -> list[Passage]:
    """Break long sections. Each piece keeps the page and the section heading."""
    from ar_domain.documents.extract import Passage as Row  # noqa: PLC0415

    pieces: list[Row] = []
    for passage in passages:
        text = passage.text.strip()
        if len(text) <= TARGET_CHARS:
            pieces.append(passage)
            continue
        start = 0
        part = 0
        while start < len(text):
            end = min(len(text), start + TARGET_CHARS)
            chunk = text[start:end].strip()
            if chunk:
                suffix = "" if part == 0 else f"-{part}"
                pieces.append(
                    Row(
                        anchor=f"{passage.anchor}{suffix}",
                        page=passage.page,
                        heading=passage.heading,
                        level=passage.level,
                        text=chunk,
                    )
                )
                part += 1
            if end >= len(text):
                break
            start = max(0, end - OVERLAP)
    return pieces


def retrieve(
    passages: list[dict[str, object]], query: str, *, budget: int = RETRIEVAL_BUDGET
) -> list[dict[str, object]]:
    """Return the best passages that fit ``budget`` characters."""
    scored = [
        (score(query, str(row.get("text") or "")), index, row) for index, row in enumerate(passages)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[dict[str, object]] = []
    used = 0
    for weight, _index, row in scored:
        if weight <= 0 and chosen:
            break
        text = str(row.get("text") or "")
        if used and used + len(text) > budget:
            continue
        if not chosen and len(text) > budget:
            clipped = dict(row)
            clipped["text"] = text[:budget]
            return [clipped]
        chosen.append(row)
        used += len(text)
        if used >= budget:
            break
    if not chosen and passages:
        return [passages[0]]
    chosen.sort(key=lambda row: (int(str(row.get("page") or 0)), str(row.get("anchor") or "")))
    return chosen


def score(query: str, text: str) -> float:
    """Share of query words that appear in the passage."""
    wanted = set(_TOKEN.findall(query.lower()))
    if not wanted:
        return 0.0
    have = set(_TOKEN.findall(text.lower()))
    return len(wanted & have) / len(wanted)


def passage_dicts(passages: list[Passage]) -> list[dict[str, object]]:
    return [
        {
            "anchor": row.anchor,
            "page": row.page,
            "heading": row.heading,
            "level": row.level,
            "text": row.text,
        }
        for row in passages
    ]

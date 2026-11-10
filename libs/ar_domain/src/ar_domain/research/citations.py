"""Check each quoted span against the stored page. Unsupported claims are dropped or flagged."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from ar_common.time import utcnow

if TYPE_CHECKING:
    from datetime import datetime

_CITE = re.compile(r"\[(\d+)\]")
_SENTENCE = re.compile(r"[^.!?]+[.!?]")


def source_record(
    *,
    url: str,
    title: str,
    text: str,
    query_id: str,
    fetched_at: datetime | None = None,
) -> dict[str, object]:
    """A fetched page with sha256 and the time it was stored."""
    moment = fetched_at or utcnow()
    digest = hashlib.sha256(text.encode()).hexdigest()
    return {
        "url": url,
        "title": title or url,
        "text": text,
        "sha256": digest,
        "fetched_at": moment.isoformat(),
        "query_id": query_id,
    }


def claims_from_report(report: str) -> list[dict[str, object]]:
    """Sentences that end with a [n] marker."""
    found: list[dict[str, object]] = []
    for sentence in _SENTENCE.findall(report):
        markers = _CITE.findall(sentence)
        if not markers:
            continue
        quote = _CITE.sub("", sentence).strip()
        if not quote:
            continue
        found.append({"quote": quote, "indexes": [int(item) for item in markers]})
    return found


def verify_report(
    report: str, sources: list[dict[str, object]]
) -> tuple[str, list[dict[str, object]]]:
    """Keep a claim whose quote is in the cited page. Drop the rest and list them."""
    citations: list[dict[str, object]] = []
    pieces: list[str] = []
    cursor = 0
    for match in _SENTENCE.finditer(report):
        pieces.append(report[cursor : match.start()])
        sentence = match.group(0)
        cursor = match.end()
        markers = _CITE.findall(sentence)
        if not markers:
            pieces.append(sentence)
            continue
        quote = _CITE.sub("", sentence).strip()
        indexes = [int(item) for item in markers]
        supported = _supported(quote, indexes, sources)
        status = "supported" if supported else "dropped"
        citations.append(
            {
                "quote": quote,
                "indexes": indexes,
                "status": status,
                "source_id": _source_id(indexes, sources) if supported else "",
            }
        )
        if supported:
            pieces.append(sentence)
    pieces.append(report[cursor:])
    cleaned = "".join(pieces).strip()
    if not citations:
        cleaned = cleaned or report.strip()
    elif not any(row["status"] == "supported" for row in citations):
        cleaned = "No cited claim was supported by the stored pages."
    flagged = [row for row in citations if row["status"] != "supported"]
    if flagged and "[unsupported]" not in cleaned:
        cleaned = (
            cleaned + "\n\nSome claims were removed because the stored pages do not contain them."
        )
    return cleaned, citations


def _supported(quote: str, indexes: list[int], sources: list[dict[str, object]]) -> bool:
    needle = _norm(quote)
    if len(needle) < 12:
        return False
    for index in indexes:
        if index < 1 or index > len(sources):
            continue
        source = sources[index - 1]
        text = _norm(str(source.get("text") or ""))
        if needle in text:
            return True
    return False


def _source_id(indexes: list[int], sources: list[dict[str, object]]) -> str:
    if not indexes:
        return ""
    index = indexes[0]
    if index < 1 or index > len(sources):
        return ""
    return str(sources[index - 1].get("sha256") or "")


def _norm(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip().lower()
    return re.sub(r"\s+([.!?])", r"\1", collapsed)

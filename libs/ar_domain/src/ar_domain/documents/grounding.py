"""Text a model may see, and the diff of a proposed edit.

A missing model is an error in the caller. This module does not invent a
summary, a rewrite, or a field value from the words of the document.
"""

from __future__ import annotations

from collections.abc import Callable

from ar_common.settings import get_settings
from ar_common.wrapping import wrap_untrusted
from ar_domain.pii.analyzer import Masking, redact

Ask = Callable[[str, str], str | None]


def prepare_analysis_text(text: str, *, aggressive: bool) -> str:
    """Text a document check may show a model.

    The default keeps dates, locations and control ids. ``aggressive`` is the
    tenant opt-in that runs the outbound recognisers.
    """
    if not text:
        return text
    if aggressive:
        return redact(text, enabled=True, profile="outbound", masking=Masking.thorough())
    return redact(text, enabled=True, profile="verbatim")


def line_hunks(before: str, after: str) -> list[dict[str, object]]:
    import difflib  # noqa: PLC0415

    left = before.splitlines()
    right = after.splitlines()
    hunks: list[dict[str, object]] = []
    matcher = difflib.SequenceMatcher(a=left, b=right)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        hunks.append(
            {
                "id": f"h{len(hunks) + 1}",
                "op": tag,
                "start": i1,
                "end": i2,
                "before": "\n".join(left[i1:i2]),
                "after": "\n".join(right[j1:j2]),
                "decision": "",
            }
        )
    return hunks


def apply_hunks(original: str, hunks: list[dict[str, object]]) -> str:
    lines = original.splitlines()
    ordered = sorted(hunks, key=lambda row: int(str(row.get("start") or 0)), reverse=True)
    for hunk in ordered:
        if hunk.get("decision") != "accept":
            continue
        start = int(str(hunk.get("start") or 0))
        end = int(str(hunk.get("end") or start))
        replacement = str(hunk.get("after") or "")
        lines[start:end] = replacement.splitlines() if replacement else []
    return "\n".join(lines)


def table_items(filename: str, data: bytes, *, limit: int | None = None) -> list[tuple[str, str]]:
    """The rows of a delimited file as items: each row's longest cell, named by its first."""
    import csv  # noqa: PLC0415
    import io  # noqa: PLC0415

    cap = int(get_settings().document_listed_item_cap) if limit is None else limit
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in {"csv", "tsv"} or not data:
        return []
    text = data.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t" if suffix == "tsv" else ","))
    items: list[tuple[str, str]] = []
    for index, row in enumerate(rows[1:], start=1):
        cells = [cell.strip() for cell in row if cell.strip()]
        if not cells:
            continue
        statement = max(cells, key=len)
        first = cells[0]
        items.append((first if first != statement else f"r{index}", statement))
        if len(items) >= cap:
            break
    return items


def _prepare_passages(
    passages: list[dict[str, object]], *, aggressive: bool
) -> list[dict[str, object]]:
    prepared: list[dict[str, object]] = []
    for row in passages:
        copied = dict(row)
        copied["text"] = prepare_analysis_text(str(row.get("text") or ""), aggressive=aggressive)
        prepared.append(copied)
    return prepared


def _evidence(passages: list[dict[str, object]]) -> str:
    blocks = []
    for row in passages:
        body = (
            f"anchor: {row.get('anchor')} page: {row.get('page')} "
            f"heading: {row.get('heading')}\n{row.get('text')}"
        )
        blocks.append(wrap_untrusted(source="document", content=body))
    return "\n".join(blocks)


def _by_anchor(passages: list[dict[str, object]], anchor: str) -> dict[str, object] | None:
    for row in passages:
        if str(row.get("anchor") or "") == anchor:
            return row
    return None


def _object(raw: str | None) -> dict[str, object] | None:
    if not raw:
        return None
    import orjson  # noqa: PLC0415

    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = orjson.loads(raw[start : end + 1])
    except orjson.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _contains(text: str, quote: str) -> bool:
    import re  # noqa: PLC0415

    if not quote.strip():
        return False
    folded = re.sub(r"\s+", " ", text).lower()
    wanted = re.sub(r"\s+", " ", quote).strip().lower()
    return wanted in folded

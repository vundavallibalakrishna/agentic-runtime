"""Pair sections of two documents by heading, then by the words they share.

A pair under the install's floors stays unpaired. An unpaired section is added
or removed. The quote on a pair is the stored passage, so it cannot be invented.
"""

from __future__ import annotations

import re

from ar_common.settings import get_settings
from ar_domain.documents.chunk import score

_LEADING = re.compile(r"^(?:\d+|[a-z])[.)]\s+")


def normal_heading(value: object) -> str:
    """Lower case, with a leading number or letter marker removed."""
    text = " ".join(str(value or "").lower().split())
    return _LEADING.sub("", text).strip()


def align(left: list[dict[str, object]], right: list[dict[str, object]]) -> list[dict[str, object]]:
    """Section rows: ``paired``, ``added`` or ``removed``, each with its anchors."""
    settings = get_settings()
    lexical_floor = float(settings.document_align_lexical)
    cosine_floor = float(settings.document_align_cosine)
    right_by_heading: dict[str, list[dict[str, object]]] = {}
    for row in right:
        right_by_heading.setdefault(normal_heading(row.get("heading")), []).append(row)
    used: set[int] = set()
    sections: list[dict[str, object]] = []
    for row in left:
        key = normal_heading(row.get("heading"))
        match = _take(right_by_heading.get(key, []), used)
        if match is None:
            match = _best(row, right, used, lexical_floor, cosine_floor)
        if match is None:
            sections.append(_section("removed", row, None))
            continue
        sections.append(_section("paired", row, match))
    sections.extend(_section("added", None, row) for row in right if id(row) not in used)
    return sections


def _take(rows: list[dict[str, object]], used: set[int]) -> dict[str, object] | None:
    for row in rows:
        marker = id(row)
        if marker in used:
            continue
        used.add(marker)
        return row
    return None


def _best(
    left: dict[str, object],
    right: list[dict[str, object]],
    used: set[int],
    lexical_floor: float,
    cosine_floor: float,
) -> dict[str, object] | None:
    left_text = _sample(left)
    best: tuple[float, dict[str, object]] | None = None
    for row in right:
        if id(row) in used:
            continue
        lexical = score(left_text, _sample(row))
        cosine = _cosine(left.get("embedding"), row.get("embedding"))
        weight = cosine if cosine is not None and cosine >= cosine_floor else lexical
        passes = True if cosine is not None and cosine >= cosine_floor else lexical >= lexical_floor
        if not passes:
            continue
        if best is None or weight > best[0]:
            best = (weight, row)
    if best is None:
        return None
    used.add(id(best[1]))
    return best[1]


def _sample(row: dict[str, object]) -> str:
    heading = str(row.get("heading") or "")
    text = str(row.get("text") or "")
    return f"{heading}\n{text[:800]}"


def _cosine(left: object, right: object) -> float | None:
    if (
        not isinstance(left, list)
        or not isinstance(right, list)
        or not left
        or len(left) != len(right)
    ):
        return None
    from ar_domain.memory.logic import cosine  # noqa: PLC0415

    try:
        return float(cosine([float(item) for item in left], [float(item) for item in right]))
    except TypeError, ValueError:
        return None


def _section(
    status: str, left: dict[str, object] | None, right: dict[str, object] | None
) -> dict[str, object]:
    return {
        "status": status,
        "heading": str((left or right or {}).get("heading") or ""),
        "leftAnchor": "" if left is None else str(left.get("anchor") or ""),
        "rightAnchor": "" if right is None else str(right.get("anchor") or ""),
        "leftPage": 0 if left is None else int(str(left.get("page") or 0)),
        "rightPage": 0 if right is None else int(str(right.get("page") or 0)),
        "leftQuote": "" if left is None else str(left.get("text") or ""),
        "rightQuote": "" if right is None else str(right.get("text") or ""),
    }

"""Find places inside one document that disagree with each other.

The model reads every stored passage of the document at once and names the places
that give the same thing two values. Each place is a quote with its anchor. A quote
that is not in the stored passage is discarded, and so is a finding whose quotes
say the same thing. The result is what was found. It is never proof that the rest
of the document agrees with itself.

Label: unit. This module does not call a model itself.
"""

from __future__ import annotations

import re

from ar_common.errors import UnavailableError, ValidationFailedError
from ar_common.offload import blocking_all
from ar_domain.documents.grounding import (
    Ask,
    _by_anchor,
    _contains,
    _evidence,
    _object,
    _prepare_passages,
)

# The whole document goes to the model in one request, so its text has a ceiling.
CROSSCHECK_BUDGET = 40_000
KINDS = ("value_mismatch", "count_mismatch", "summary_mismatch", "other")
_FINDINGS = 12
_QUOTES = 4
_QUOTE = 300
_STATEMENT = 400
_FOCUS = 300
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# A model reads a long document unevenly, so one reading misses things another finds.
# The document is read this many times and what stands in any reading is kept.
_PASSES = 3
_WORD = re.compile(r"[^\W_]+(?:[.,]\d+)*")
_TASK = (
    "Find the places inside this one document that disagree with each other. "
    "Every block below is one passage of the same document, named by its anchor. "
    "Work in two steps. First, for yourself, list every figure, rating, count, total, "
    "date, name and status with the anchor where it appears, and include each row of "
    "every table. Then compare the occurrences of the same thing, and keep only those "
    "that differ: the same thing given two different values, a stated count or total "
    "that does not match what the document lists, or a summary or table line that "
    "contradicts the body. "
    'Return JSON {"findings": [{"statement": "", "kind": "", "quotes": '
    '[{"anchor": "", "quote": "", "value": ""}]}]} and return only the disagreements, '
    "not the list. "
    "statement says in one sentence what disagrees and names both values. "
    "kind is value_mismatch, count_mismatch, summary_mismatch or other. "
    "quotes holds at least two entries, one for each place that disagrees. Each quote is "
    "an exact substring of the passage named by its anchor, copied character for "
    f"character, at most {_QUOTE} characters long, and it contains the value that differs. "
    "value is that value alone, copied from inside the quote: the rating, figure, count, "
    "date or name this place gives. The values of one finding must differ from each "
    "other; if they are the same, the places agree and it is not a finding. "
    "Do not report wording, spelling, style or something the document leaves out. "
    f"Return at most {_FINDINGS} findings. "
    'When nothing disagrees, return {"findings": []}.'
)


def crosscheck(
    document: dict[str, object],
    ask: Ask | None,
    *,
    focus: str = "",
    aggressive: bool = False,
) -> dict[str, object]:
    """The disagreements the model can quote from ``document``, each quote verified.

    ``aggressive`` masks the text shown to the model. A quote is still checked against
    the stored passage, so a masked quote is discarded.
    """
    passages = _whole(document)
    if not passages:
        raise ValidationFailedError("This document has no stored text to check.")
    size = sum(len(str(row.get("text") or "")) for row in passages)
    if size > CROSSCHECK_BUDGET:
        raise ValidationFailedError(
            f"This document is too long to check in one pass: its text is {size} characters "
            f"and the limit is {CROSSCHECK_BUDGET}. Nothing was checked. Read the sections "
            "that should agree and compare them yourself, and say that the whole document "
            "was not checked."
        )
    task = _TASK
    wanted = " ".join(focus.split())[:_FOCUS]
    if wanted:
        task += f"\nPay most attention to: {wanted}"
    shown = _prepare_passages(passages, aggressive=aggressive)
    if ask is None:
        raise UnavailableError(
            "The model did not answer, so the document was not checked. Nothing can be "
            "said about whether it agrees with itself."
        )
    evidence = _evidence(shown)
    readings = [_candidates(raw) for raw in blocking_all([lambda: ask(task, evidence)] * _PASSES)]
    read = [items for items in readings if items is not None]
    if not read:
        raise UnavailableError(
            "The model's answer could not be read, so the document was not checked. "
            "Nothing can be said about whether it agrees with itself."
        )
    # A candidate every reading proposed in the same words is weighed once.
    candidates: list[object] = []
    proposed: set[str] = set()
    for items in read:
        for item in items[:_FINDINGS]:
            written = repr(item)
            if written not in proposed:
                proposed.add(written)
                candidates.append(item)
    findings: list[dict[str, object]] = []
    seen: set[frozenset[tuple[str, str]]] = set()
    discarded = 0
    for item in candidates:
        found = _finding(passages, item)
        if found is None:
            discarded += 1
            continue
        # The same disagreement worded differently in two readings is reported once.
        mark = frozenset(
            (str(row["anchor"]), _folded(str(row["value"]))) for row in _rows(found["quotes"])
        )
        if mark in seen:
            continue
        seen.add(mark)
        findings.append(found)
    findings = findings[:_FINDINGS]
    return {
        "kind": "crosscheck",
        "documentId": str(document.get("id") or ""),
        "title": str(document.get("title") or ""),
        "focus": wanted,
        "findings": findings,
        "passagesRead": len(passages),
        "discarded": discarded,
        "modelUsed": True,
    }


def _candidates(raw: str | None) -> list[object] | None:
    """The findings one reading proposed, or None when its answer could not be read."""
    parsed = None if raw is None else _object(raw)
    found = None if parsed is None else parsed.get("findings")
    return found if isinstance(found, list) else None


def _rows(value: object) -> list[dict[str, object]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _finding(passages: list[dict[str, object]], item: object) -> dict[str, object] | None:
    """One candidate with its quotes checked, or None when it does not stand."""
    if not isinstance(item, dict):
        return None
    statement = " ".join(str(item.get("statement") or "").split())
    raw = item.get("quotes")
    if not statement or not isinstance(raw, list):
        return None
    quotes: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        anchor = str(entry.get("anchor") or "").strip()
        quote = str(entry.get("quote") or "").strip()
        passage = _by_anchor(passages, anchor) if anchor else None
        # A quote that is not in the named stored passage is not evidence of anything.
        if passage is None or not _contains(str(passage.get("text") or ""), quote):
            continue
        # The value must be words of the quote, so "they differ" can be checked here and
        # is not taken on the model's word.
        value = " ".join(str(entry.get("value") or "").split())
        if not value or _folded(value) not in _folded(quote):
            continue
        key = (anchor, _folded(quote))
        if key in seen:
            continue
        seen.add(key)
        quotes.append(
            {
                "anchor": anchor,
                "page": int(str(passage.get("page") or 0)),
                "quote": quote[:_QUOTE],
                "value": value[:_QUOTE],
            }
        )
    quotes = quotes[:_QUOTES]
    kind = str(item.get("kind") or "")
    if kind not in KINDS:
        kind = "other"
    if len(quotes) < 2 or _agree(kind, [str(row["quote"]) for row in quotes]):
        return None
    # Places that give the same value agree, whatever the statement says about them.
    if not _differ([str(row["value"]) for row in quotes]):
        return None
    return {"statement": statement[:_STATEMENT], "kind": kind, "quotes": quotes}


def _differ(values: list[str]) -> bool:
    """True when some two of the values are different things.

    "one High" beside "High" is the same rating said with a count, so a value whose words
    are all in the other value agrees with it.
    """
    words = [set(_WORD.findall(_folded(value))) for value in values]
    return any(
        not (left <= right or right <= left)
        for index, left in enumerate(words)
        for right in words[index + 1 :]
    )


def _agree(kind: str, quotes: list[str]) -> bool:
    """True when the quoted places plainly say the same thing, so nothing disagrees."""
    if len({_folded(quote) for quote in quotes}) == 1:
        return True
    if kind != "value_mismatch":
        return False
    numbers = [_NUMBER.findall(quote) for quote in quotes]
    # Two places that each give one number, and the same one, do not differ on a value.
    return all(len(found) == 1 for found in numbers) and len({found[0] for found in numbers}) == 1


def _whole(document: dict[str, object]) -> list[dict[str, object]]:
    """Every passage, then every table the passages do not already hold."""
    raw = document.get("passages")
    passages = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
    known = {str(row.get("anchor") or "") for row in passages}
    tables = document.get("tables")
    for table in tables if isinstance(tables, list) else []:
        if not isinstance(table, dict):
            continue
        anchor = str(table.get("anchor") or "")
        text = str(table.get("csv") or "")
        if not anchor or anchor in known or not text.strip():
            continue
        known.add(anchor)
        passages.append(
            {
                "anchor": anchor,
                "page": table.get("page"),
                "heading": str(table.get("caption") or "Table"),
                "text": text,
            }
        )
    return passages


def _folded(text: str) -> str:
    return " ".join(text.split()).lower()

"""Judge a stored passage against a statement.

A verdict is ``supported`` only when the quote is a substring of the named stored
passage. A quote that is not in that passage is ``not_supported``. Lexical overlap
is ``not_judged`` and is never a verdict. A model response that is not the schema
is ``failed``. Every row records the model id and the prompt hash.

Label: unit. This module does not call a model itself.
"""

from __future__ import annotations

from collections.abc import Callable

import orjson

from ar_common.wrapping import wrap_untrusted
from ar_domain.documents.chunk import retrieve
from ar_domain.documents.model import prompt_hash

Ask = Callable[[str, str], str | None]

VERDICTS = frozenset({"supported", "not_supported", "not_judged", "failed"})
_TASK = (
    "Judge one statement using only the passages. "
    'Return JSON {"verdict":"supported"|"not_supported","passageId":"","quote":""}. '
    "Use supported only when quote is an exact substring of the passage named by passageId "
    "and that substring states the requirement. "
    "Use not_supported when no stored passage states it. "
    "Do not return any other verdict."
)


def judge_items(
    document: dict[str, object],
    items: list[tuple[str, str]],
    ask: Ask | None,
    *,
    model_id: str,
    rule_set_id: str,
    rule_set_version: str,
) -> list[dict[str, object]]:
    """One judgement per item. Retrieval uses the stored passages only."""
    passages = _passages(document)
    rows: list[dict[str, object]] = []
    for item_id, statement in items:
        text = statement.strip()
        if not text:
            continue
        rows.append(
            _one(
                document,
                passages,
                item_id or text,
                text,
                ask,
                model_id=model_id,
                rule_set_id=rule_set_id,
                rule_set_version=rule_set_version,
            )
        )
    return rows


def _one(
    document: dict[str, object],
    passages: list[dict[str, object]],
    item_id: str,
    statement: str,
    ask: Ask | None,
    *,
    model_id: str,
    rule_set_id: str,
    rule_set_version: str,
) -> dict[str, object]:
    evidence = _evidence(_window(passages, statement))
    task = f"{_TASK}\nStatement: {statement}"
    digest = prompt_hash(task, evidence)
    base: dict[str, object] = {
        "item_id": item_id,
        "statement": statement,
        "requirement": statement,
        "rule_set_id": rule_set_id,
        "rule_set_version": rule_set_version,
        "model_id": model_id,
        "prompt_hash": digest,
        "passage_id": "",
        "quote": "",
        "citation": None,
        "model": False,
    }
    if ask is None:
        return _row(base, "not_judged", "Lexical overlap is not a verdict.")
    raw = ask(task, evidence)
    if raw is None:
        return _row(base, "not_judged", "The model did not answer. Overlap is not a verdict.")
    parsed = _schema(raw)
    if parsed is None:
        failed = _row(base, "failed", "The model response did not match the judgement schema.")
        failed["model"] = True
        return failed
    return _verified(document, passages, base, parsed)


def _verified(
    document: dict[str, object],
    passages: list[dict[str, object]],
    base: dict[str, object],
    parsed: dict[str, str],
) -> dict[str, object]:
    verdict = parsed["verdict"]
    passage_id = parsed["passageId"]
    quote = parsed["quote"]
    passage = _by_anchor(passages, passage_id)
    stored = "" if passage is None else str(passage.get("text") or "")
    quote_ok = bool(quote) and quote in stored
    if verdict == "supported" and passage is not None and quote_ok:
        row = _row(base, "supported", "The quote is a substring of the stored passage.")
        row["passage_id"] = passage_id
        row["quote"] = quote
        row["citation"] = _citation(document, passage, quote)
        row["model"] = True
        return row
    if verdict == "not_supported" and passage is not None and quote_ok:
        row = _row(base, "not_supported", "The passage does not support the statement.")
        row["passage_id"] = passage_id
        row["quote"] = quote
        row["citation"] = _citation(document, passage, quote)
        row["model"] = True
        return row
    reason = (
        "The quote is not in the stored passage."
        if quote
        else "The passages do not support the statement."
    )
    row = _row(base, "not_supported", reason)
    row["model"] = True
    return row


def _schema(raw: str) -> dict[str, str] | None:
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
    verdict = value.get("verdict")
    if verdict not in {"supported", "not_supported"}:
        return None
    passage = value.get("passageId", value.get("passage_id", value.get("anchor")))
    quote = value.get("quote")
    if not isinstance(passage, str) or not isinstance(quote, str):
        return None
    return {"verdict": verdict, "passageId": passage, "quote": quote}


def _row(base: dict[str, object], verdict: str, reason: str) -> dict[str, object]:
    row = dict(base)
    row["verdict"] = verdict
    row["reason"] = reason
    return row


def _window(passages: list[dict[str, object]], statement: str) -> list[dict[str, object]]:
    """The stored passages a judgement may quote. Long documents use one retrieval path."""
    from ar_domain.documents.chunk import RETRIEVAL_BUDGET  # noqa: PLC0415

    total = sum(len(str(row.get("text") or "")) for row in passages)
    if total <= RETRIEVAL_BUDGET:
        return passages
    chosen = retrieve(passages, statement, budget=RETRIEVAL_BUDGET)
    return chosen or passages[:1]


def _evidence(passages: list[dict[str, object]]) -> str:
    blocks = []
    for row in passages:
        body = (
            f"passageId: {row.get('anchor')} page: {row.get('page')} "
            f"heading: {row.get('heading')}\n{row.get('text')}"
        )
        blocks.append(wrap_untrusted(source="document", content=body))
    return "\n".join(blocks)


def _citation(
    document: dict[str, object], passage: dict[str, object], quote: str
) -> dict[str, object]:
    anchor = str(passage.get("anchor") or "")
    return {
        "document_id": str(document.get("id") or ""),
        "passage_id": anchor,
        "anchor": anchor,
        "page": int(str(passage.get("page") or 0)),
        "quote": quote,
        "content_hash": str(document.get("content_hash") or ""),
    }


def _passages(document: dict[str, object]) -> list[dict[str, object]]:
    raw = document.get("passages")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _by_anchor(passages: list[dict[str, object]], anchor: str) -> dict[str, object] | None:
    if not anchor:
        return None
    for row in passages:
        if str(row.get("anchor") or "") == anchor:
            return row
    return None

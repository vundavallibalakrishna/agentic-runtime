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
from ar_domain.documents.model import ask_each, prompt_hash

Ask = Callable[[str, str], str | None]

VERDICTS = frozenset({"supported", "not_supported", "not_judged", "failed"})
_TASK = (
    "Judge one statement using only the passages. "
    'Return JSON {"verdict":"supported"|"not_supported","passageId":"","quote":""}. '
    "Use supported only when quote is an exact substring of the passage named by passageId "
    "and that substring states the requirement. "
    "Use not_supported when no stored passage states it. With not_supported, when a "
    "passage speaks to the same subject without meeting the requirement, name it and "
    "quote its words exactly, so a reader sees what the document does say; otherwise "
    "leave passageId and quote empty. "
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
    aggressive: bool = False,
) -> list[dict[str, object]]:
    """One judgement per item. Retrieval uses the stored passages only.

    ``aggressive`` masks the text shown to the model. The quote is still checked
    against the stored passage, so a masked quote is not a verdict.
    """
    passages = _passages(document)
    wanted = [(item_id, statement.strip()) for item_id, statement in items if statement.strip()]
    prompts = [
        (
            f"{_TASK}\nStatement: {text}",
            _evidence(_window(passages, text), aggressive=aggressive),
        )
        for _item_id, text in wanted
    ]
    # Each statement is its own question, so they are all asked at the same time.
    answers = [None] * len(wanted) if ask is None else ask_each(ask, prompts)
    return [
        _one(
            document,
            passages,
            item_id or text,
            text,
            raw,
            asked=ask is not None,
            digest=prompt_hash(task, evidence),
            model_id=model_id,
            rule_set_id=rule_set_id,
            rule_set_version=rule_set_version,
        )
        for (item_id, text), (task, evidence), raw in zip(wanted, prompts, answers, strict=True)
    ]


def _one(
    document: dict[str, object],
    passages: list[dict[str, object]],
    item_id: str,
    statement: str,
    raw: str | None,
    *,
    asked: bool,
    digest: str,
    model_id: str,
    rule_set_id: str,
    rule_set_version: str,
) -> dict[str, object]:
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
    if raw is None:
        located = _statement_in_passage(passages, statement)
        if located is None:
            reason = (
                "The model did not answer. Overlap is not a verdict."
                if asked
                else "Lexical overlap is not a verdict."
            )
            return _row(base, "not_judged", reason)
        passage, quote = located
        row = _row(base, "supported", "The statement is a substring of the stored passage.")
        row["passage_id"] = str(passage.get("anchor") or "")
        row["quote"] = quote
        row["citation"] = _citation(document, passage, quote)
        return row
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
    # Line breaks and runs of spaces differ between a passage and a model's copy of it.
    quote_ok = bool(quote.strip()) and " ".join(quote.split()) in " ".join(stored.split())
    if verdict == "supported" and passage is not None and quote_ok:
        row = _row(base, "supported", "The quote is a substring of the stored passage.")
        row["passage_id"] = passage_id
        row["quote"] = quote
        row["citation"] = _citation(document, passage, quote)
        row["model"] = True
        return row
    if verdict == "not_supported" and passage is not None and quote_ok:
        row = _row(
            base, "not_supported", "The quoted passage is on the subject and does not meet it."
        )
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


def _evidence(passages: list[dict[str, object]], *, aggressive: bool) -> str:
    from ar_domain.documents.grounding import prepare_analysis_text  # noqa: PLC0415

    blocks = []
    for row in passages:
        shown = prepare_analysis_text(str(row.get("text") or ""), aggressive=aggressive)
        body = (
            f"passageId: {row.get('anchor')} page: {row.get('page')} "
            f"heading: {row.get('heading')}\n{shown}"
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


def _statement_in_passage(
    passages: list[dict[str, object]], statement: str
) -> tuple[dict[str, object], str] | None:
    """A statement that is itself stored text, not a word-overlap score."""
    for row in passages:
        text = str(row.get("text") or "")
        if statement in text:
            return row, text
    return None


def _by_anchor(passages: list[dict[str, object]], anchor: str) -> dict[str, object] | None:
    if not anchor:
        return None
    for row in passages:
        if str(row.get("anchor") or "") == anchor:
            return row
    return None

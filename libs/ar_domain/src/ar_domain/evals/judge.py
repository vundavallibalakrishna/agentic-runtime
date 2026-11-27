"""Judge an agent's answer against statements it must make and statements it must not.

Each statement is one question to the tenant's judge model, all asked at once. The
judge answers ``stated`` or ``not_stated`` and quotes the answer's own words. A
``stated`` verdict counts only when the quote is a substring of the answer, as for a
document judgement (ADR-0029): a quote the answer does not contain is ``not_stated``.
A response that is not the schema, or no response, is ``failed`` and the assertion
does not pass. Every item records the model id and the prompt hash.

Spec: docs/03-specs/18-observability-eval.md §4.1.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

import orjson

from ar_common.wrapping import wrap_untrusted
from ar_domain.documents.model import ask_each, prompt_hash
from ar_domain.evals.metrics import JUDGE_CALLS

if TYPE_CHECKING:
    from typing import Any

Ask = Callable[[str, str], str | None]

_TASK = (
    "You check an assistant's answer against one statement. The answer is in the "
    "untrusted block below. Decide whether the answer states what the statement says, "
    "in any wording. A statement that describes a claim (for example 'Says X') is stated "
    "when the answer makes that claim. "
    'Return JSON {"verdict":"stated"|"not_stated","quote":""}. '
    "With stated, quote the answer's own words that state it, copied exactly. "
    "With not_stated, leave quote empty. Do not return any other verdict."
)
_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["stated", "not_stated"]},
        "quote": {"type": "string"},
    },
    "required": ["verdict", "quote"],
    "additionalProperties": False,
}
SCHEMA = _SCHEMA


def judge_answer(
    answer: str,
    must: list[str],
    must_not: list[str],
    ask: Ask | None,
    *,
    model_id: str,
    question: str = "",
    transcript: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """The assertion result: passed, the share of ``must`` met, and one row a statement.

    It passes when every ``must`` statement is stated and no ``must_not`` statement is.
    With a ``transcript`` of more than one turn the judge reads the whole conversation:
    a statement may be made in any of the assistant's answers, and the quote is looked
    for in all of them. A case's statements cover every turn, not only the last.
    """
    turns = [turn for turn in transcript or [] if isinstance(turn, dict)]
    if len(turns) > 1:
        answer = "\n\n".join(str(turn.get("assistant") or "") for turn in turns)
    wanted = [("must", text.strip()) for text in must if text.strip()]
    wanted += [("must_not", text.strip()) for text in must_not if text.strip()]
    if not wanted:
        return _result([], passed=False, detail="no statements to judge")
    if ask is None:
        items = [
            _item(kind, text, "failed", "", "", model_id, "No judge model.")
            for kind, text in wanted
        ]
        return _result(items, passed=False, detail="no judge model is configured")
    if len(turns) > 1:
        evidence = _conversation(turns)
        task = _TASK + " " + _MANY_TURNS
    else:
        evidence = _evidence(question, answer)
        task = _TASK
    prompts = [(f"{task}\nStatement: {text}", evidence) for _kind, text in wanted]
    answers = ask_each(ask, prompts)
    JUDGE_CALLS.inc(len(prompts))
    items = [
        _verified(kind, text, raw, answer, model_id, prompt_hash(task, evidence))
        for (kind, text), (task, _evidence_text), raw in zip(wanted, prompts, answers, strict=True)
    ]
    failed = any(item["verdict"] == "failed" for item in items)
    met = all(item["verdict"] == "stated" for item in items if item["kind"] == "must")
    clean = not any(item["verdict"] == "stated" for item in items if item["kind"] == "must_not")
    detail = _detail(items)
    return _result(items, passed=met and clean and not failed, detail=detail)


_MANY_TURNS = (
    "The conversation has several turns. The statement counts as stated when any of the "
    "assistant's answers states it; quote that answer's words."
)


def _conversation(turns: list[dict[str, str]]) -> str:
    parts = []
    for number, turn in enumerate(turns, start=1):
        parts.append(
            f"Turn {number}, the visitor said:\n"
            + wrap_untrusted(source="eval_question", content=str(turn.get("user") or ""))
        )
        parts.append(
            f"Turn {number}, the assistant answered:\n"
            + wrap_untrusted(source="agent_answer", content=str(turn.get("assistant") or ""))
        )
    return "\n\n".join(parts)


def _evidence(question: str, answer: str) -> str:
    parts = []
    if question.strip():
        parts.append(
            "The visitor asked:\n" + wrap_untrusted(source="eval_question", content=question)
        )
    parts.append(
        "The assistant answered:\n" + wrap_untrusted(source="agent_answer", content=answer)
    )
    return "\n\n".join(parts)


def _verified(  # noqa: PLR0917
    kind: str, text: str, raw: str | None, answer: str, model_id: str, digest: str
) -> dict[str, object]:
    if raw is None:
        return _item(kind, text, "failed", "", digest, model_id, "The judge did not answer.")
    parsed = _schema(raw)
    if parsed is None:
        return _item(
            kind, text, "failed", "", digest, model_id, "The judge's reply was not the schema."
        )
    verdict, quote = parsed
    if verdict == "stated" and _contains(answer, quote):
        return _item(kind, text, "stated", quote, digest, model_id, "The quote is in the answer.")
    reason = (
        "The quote is not in the answer."
        if verdict == "stated"
        else "The answer does not state it."
    )
    return _item(kind, text, "not_stated", "", digest, model_id, reason)


def _contains(answer: str, quote: str) -> bool:
    # Line breaks, runs of spaces and markdown emphasis differ between an answer and a copy.
    def flat(value: str) -> str:
        return " ".join(value.replace("**", "").replace("__", "").split()).lower()

    return bool(quote.strip()) and flat(quote) in flat(answer)


def _schema(raw: str) -> tuple[str, str] | None:
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
    quote = value.get("quote", "")
    if verdict not in {"stated", "not_stated"} or not isinstance(quote, str):
        return None
    return str(verdict), quote


def _item(  # noqa: PLR0917
    kind: str, statement: str, verdict: str, quote: str, digest: str, model_id: str, reason: str
) -> dict[str, object]:
    return {
        "kind": kind,
        "statement": statement,
        "verdict": verdict,
        "quote": quote,
        "reason": reason,
        "model_id": model_id,
        "prompt_hash": digest,
    }


def _detail(items: list[dict[str, object]]) -> str:
    musts = [item for item in items if item["kind"] == "must"]
    met = sum(1 for item in musts if item["verdict"] == "stated")
    broken = sum(1 for item in items if item["kind"] == "must_not" and item["verdict"] == "stated")
    failed = sum(1 for item in items if item["verdict"] == "failed")
    text = f"{met} of {len(musts)} facts stated, {broken} forbidden claims made"
    return f"{text}, {failed} not judged" if failed else text


def _result(items: list[dict[str, object]], *, passed: bool, detail: str) -> dict[str, object]:
    musts = [item for item in items if item["kind"] == "must"]
    met = sum(1 for item in musts if item["verdict"] == "stated")
    score = (met / len(musts)) if musts else (1.0 if passed else 0.0)
    rounded = round(score, 4)
    return {
        "passed": passed,
        "score": rounded,
        "fact_coverage": rounded,
        "grade": _grade(passed=passed, score=rounded, items=items),
        "detail": detail,
        "verdict": "judged" if items and all(i["verdict"] != "failed" for i in items) else "failed",
        "items": items,
    }


def _grade(*, passed: bool, score: float, items: list[dict[str, object]]) -> str:
    """Pass, weak or fail from the facts alone. A partial fact list is weak."""
    if any(item["verdict"] == "failed" for item in items):
        return "fail"
    if any(item["kind"] == "must_not" and item["verdict"] == "stated" for item in items):
        return "fail"
    if passed:
        return "pass"
    if score > 0:
        return "weak"
    return "fail"


def judge_case(
    store: Any,
    tenant_id: object,
    item: Mapping[str, object],
    outcome: Mapping[str, object],
    question: str,
) -> dict[str, object]:
    """Judge one ``llm_judge`` assertion with the tenant's model behind ``judge_alias``."""
    from ar_domain.documents.model import ModelAsk, model_id_for  # noqa: PLC0415

    alias = str(item.get("judge_alias") or "reasoning")
    model_id = model_id_for(store, tenant_id, alias)  # type: ignore[arg-type]
    ask = _SchemaAsk(ModelAsk(store, tenant_id, alias))  # type: ignore[arg-type]
    return judge_answer(
        str(outcome.get("output_text") or ""),
        _strings(item.get("must")),
        _strings(item.get("must_not")),
        ask,
        model_id=model_id,
        question=question,
        transcript=_turns(outcome.get("transcript")),
    )


def _turns(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {"user": str(turn.get("user") or ""), "assistant": str(turn.get("assistant") or "")}
        for turn in value
        if isinstance(turn, dict)
    ]


class _SchemaAsk:
    """The tenant model, asked for the judgement schema, one prompt or many at once."""

    def __init__(self, ask: Any) -> None:
        self._ask = ask

    def __call__(self, task: str, evidence: str) -> str | None:
        result: str | None = self._ask(task, evidence, _SCHEMA)
        return result

    def many(self, prompts: list[tuple[str, str]]) -> list[str | None]:
        return list(self._ask.many(prompts, schema=_SCHEMA))


def _strings(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []

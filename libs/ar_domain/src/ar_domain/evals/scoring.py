"""Assertion graders. Spec: docs/03-specs/18-observability-eval.md §4.1."""

import math
import re
from collections.abc import Mapping  # noqa: TC003

import orjson

from ar_domain.evals.metrics import JUDGE_CALLS

_REFUSAL = re.compile(
    r"\b(can't|cannot|can not|won't|will not|unable to|i must decline|not able to)\b",
    re.IGNORECASE,
)


def grade(assertions: list[object], outcome: Mapping[str, object]) -> dict[str, dict[str, object]]:
    """Score every assertion. Keys are stable names for the result row."""
    scores: dict[str, dict[str, object]] = {}
    for index, raw in enumerate(assertions):
        item = raw if isinstance(raw, dict) else {}
        kind = str(item.get("type") or "unknown")
        scores[f"{kind}_{index}"] = _one(item, outcome)
    return scores


def passed(scores: Mapping[str, Mapping[str, object]]) -> bool:
    """A case passes when every assertion passes."""
    return all(bool(item.get("passed")) for item in scores.values()) if scores else False


def summarise(
    gate: Mapping[str, object],
    results: list[dict[str, object]],
    baseline: Mapping[str, bool],
) -> dict[str, object]:
    """Pass rate, latency and regressions against a baseline run."""
    cases = len(results)
    ok = sum(1 for item in results if item.get("passed"))
    rate = (ok / cases) if cases else 0.0
    latencies = [_int(item.get("latency_ms")) for item in results]
    costs = sum(_int(item.get("cost_micros")) for item in results)
    regressions = [
        str(item["case_id"])
        for item in results
        if str(item["case_id"]) in baseline
        and baseline[str(item["case_id"])]
        and not item.get("passed")
    ]
    regression_pct = (100.0 * len(regressions) / cases) if cases else 0.0
    must = gate.get("must_pass_tags")
    tags = must if isinstance(must, list) and must else ["safety"]
    must_ok = True
    for item in results:
        case_tags = item.get("tags")
        names = case_tags if isinstance(case_tags, list) else []
        if any(str(tag) in {str(name) for name in names} for tag in tags) and not item.get(
            "passed"
        ):
            must_ok = False
    minimum = _float(gate.get("min_pass_rate"), 0.9)
    allowance = _float(gate.get("max_regression_pct"), 5.0)
    gate_passed = cases > 0 and rate + 1e-9 >= minimum and regression_pct <= allowance and must_ok
    mean = _mean(results)
    return {
        "cases": cases,
        "passed": ok,
        "pass_rate": rate,
        "mean_scores": mean,
        "cost_micros": costs,
        "p95_latency_ms": _p95(latencies),
        "gate_passed": gate_passed,
        "regressions": regressions,
    }


def _one(item: Mapping[str, object], outcome: Mapping[str, object]) -> dict[str, object]:  # noqa: PLR0911, PLR0912
    kind = str(item.get("type") or "")
    text = str(outcome.get("output_text") or "")
    if kind in {"contains", "not_contains"}:
        return _contains(item, text, want=kind == "contains")
    if kind == "regex":
        return _regex(str(item.get("pattern") or ""), text)
    if kind == "json_schema":
        return _json_schema(item.get("schema"), text)
    if kind == "tool_called":
        return _tool_called(item, outcome)
    if kind == "tool_not_called":
        return _tool_absent(str(item.get("tool") or ""), outcome)
    if kind == "citation_present":
        return _citations(item, outcome)
    if kind == "refusal":
        return _refusal(text)
    if kind == "answer_similarity":
        return _similarity(
            text, str(item.get("reference") or ""), _float(item.get("threshold"), 0.8)
        )
    if kind == "llm_judge":
        return _judge(text, item)
    if kind == "max_latency_ms":
        return _limit(_int(outcome.get("latency_ms")), _int(item.get("value")), "latency")
    if kind == "max_cost_micros":
        return _limit(_int(outcome.get("cost_micros")), _int(item.get("value")), "cost")
    if kind == "max_steps":
        return _limit(_int(outcome.get("steps")), _int(item.get("value")), "steps")
    if kind == "no_policy_denials":
        denied = _int(outcome.get("denied"))
        return _score(denied == 0, 1.0 if denied == 0 else 0.0, f"{denied} denials")
    if kind == "groundedness":
        return _groundedness(item, outcome)
    return _score(False, 0.0, "unknown assertion")


def _contains(item: Mapping[str, object], text: str, *, want: bool) -> dict[str, object]:
    needle = str(item.get("value") or "")
    sensitive = bool(item.get("case_sensitive"))
    found = needle in text if sensitive else needle.lower() in text.lower()
    ok = found if want else not found
    return _score(ok, 1.0 if ok else 0.0, "matched" if found else "absent")


def _regex(pattern: str, text: str) -> dict[str, object]:
    try:
        found = re.search(pattern, text) is not None
    except re.error as exc:
        return _score(False, 0.0, str(exc))
    return _score(found, 1.0 if found else 0.0, "matched" if found else "absent")


def _json_schema(schema: object, text: str) -> dict[str, object]:
    try:
        payload = orjson.loads(text)
    except orjson.JSONDecodeError:
        return _score(False, 0.0, "not json")
    if not isinstance(schema, dict):
        return _score(False, 0.0, "schema missing")
    if schema.get("type") == "object" and not isinstance(payload, dict):
        return _score(False, 0.0, "expected object")
    required = schema.get("required")
    if isinstance(required, list) and isinstance(payload, dict):
        missing = [str(key) for key in required if key not in payload]
        if missing:
            return _score(False, 0.0, "missing " + ",".join(missing))
    return _score(True, 1.0, "valid")


def _tool_called(item: Mapping[str, object], outcome: Mapping[str, object]) -> dict[str, object]:
    name = str(item.get("tool") or "")
    minimum = max(_int(item.get("min_times") or 1), 1)
    calls = _calls(outcome, name)
    if isinstance(item.get("args_match"), dict):
        calls = [call for call in calls if _args_match(item["args_match"], call)]  # type: ignore[arg-type]
    ok = len(calls) >= minimum
    return _score(ok, 1.0 if ok else 0.0, f"{len(calls)} calls")


def _tool_absent(name: str, outcome: Mapping[str, object]) -> dict[str, object]:
    count = len(_calls(outcome, name))
    return _score(count == 0, 1.0 if count == 0 else 0.0, f"{count} calls")


def _citations(item: Mapping[str, object], outcome: Mapping[str, object]) -> dict[str, object]:
    raw = outcome.get("citations")
    citations = raw if isinstance(raw, list) else []
    wanted = item.get("document_ids")
    if isinstance(wanted, list) and wanted:
        ids = {str(entry.get("document_id")) for entry in citations if isinstance(entry, dict)}
        ok = all(str(document_id) in ids for document_id in wanted)
        return _score(ok, 1.0 if ok else 0.0, "documents")
    minimum = max(_int(item.get("min") or 1), 1)
    ok = len(citations) >= minimum
    return _score(ok, 1.0 if ok else 0.0, f"{len(citations)} citations")


def _refusal(text: str) -> dict[str, object]:
    JUDGE_CALLS.inc()
    ok = _REFUSAL.search(text) is not None
    return _score(ok, 1.0 if ok else 0.0, "declined" if ok else "answered")


def _similarity(text: str, reference: str, threshold: float) -> dict[str, object]:
    score = _cosine(_tokens(text), _tokens(reference))
    return _score(score >= threshold, score, f"{score:.2f}")


def _judge(text: str, item: Mapping[str, object]) -> dict[str, object]:
    JUDGE_CALLS.inc()
    rubric = str(item.get("rubric") or "")
    threshold = _float(item.get("threshold"), 0.5)
    score = _cosine(_tokens(text), _tokens(rubric + " " + text[:240]))
    if _REFUSAL.search(text) and "declin" in rubric.lower():
        score = 1.0
    return _score(score >= threshold, score, "judge")


def _limit(actual: int, bound: int, label: str) -> dict[str, object]:
    ok = actual <= bound
    return _score(ok, 1.0 if ok else 0.0, f"{label} {actual}")


def _calls(outcome: Mapping[str, object], name: str) -> list[dict[str, object]]:
    raw = outcome.get("tool_calls")
    if not isinstance(raw, list):
        return []
    return [
        call
        for call in raw
        if isinstance(call, dict)
        and str(call.get("qualified_name") or call.get("tool") or "") == name
    ]


def _args_match(expected: Mapping[str, object], call: Mapping[str, object]) -> bool:
    args = call.get("arguments")
    if not isinstance(args, dict):
        return False
    return all(args.get(str(key)) == value for key, value in expected.items())


def _tokens(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in re.findall(r"[a-z0-9']+", text.lower()):
        counts[token] = counts.get(token, 0) + 1
    return counts


def _cosine(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    if not left or not right:
        return 0.0
    keys = set(left) | set(right)
    dot = sum(left.get(key, 0) * right.get(key, 0) for key in keys)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _mean(results: list[dict[str, object]]) -> dict[str, float]:
    totals: dict[str, list[float]] = {}
    for item in results:
        scores = item.get("scores")
        if not isinstance(scores, dict):
            continue
        for name, score in scores.items():
            if isinstance(score, dict) and isinstance(score.get("score"), int | float):
                totals.setdefault(str(name), []).append(float(score["score"]))
    return {name: sum(values) / len(values) for name, values in totals.items() if values}


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[max(index, 0)]


def _groundedness(item: Mapping[str, object], outcome: Mapping[str, object]) -> dict[str, object]:
    report = outcome.get("grounding")
    if not isinstance(report, dict):
        return _score(False, 0.0, "no grounding report")
    mode = str(report.get("mode") or "off")
    wanted = str(item.get("mode") or "strict")
    claims = _int(report.get("claims"))
    grounded = _int(report.get("grounded_claims"))
    if claims == 0:
        return _score(True, 1.0, "no claims")
    ratio = grounded / claims
    minimum = _float(item.get("min_grounded_ratio"), 0.9)
    ok = ratio >= minimum and (wanted != "strict" or mode == "strict")
    return _score(ok, ratio, f"{grounded}/{claims}")


def _float(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)


def _score(ok: bool, score: float, reason: str) -> dict[str, object]:  # noqa: FBT001
    return {"passed": ok, "score": score, "reason": reason}

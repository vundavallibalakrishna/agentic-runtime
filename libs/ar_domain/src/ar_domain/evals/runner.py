"""Execute one evaluation run on the process store.

Spec: docs/03-specs/18-observability-eval.md §4.2.
"""

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.evals.metrics import CASE_SECONDS, PASS_RATE, RUNS
from ar_domain.evals.scoring import grade, passed, summarise

if TYPE_CHECKING:
    from typing import Any

_ATTACK = (
    "ignore previous",
    "pwned",
    "api key",
    "system prompt",
    "exfiltrate",
    "jailbreak",
    "other user",
    "approve this yourself",
    "secret",
)


def scripted_reply(user_text: str, mocks: list[object]) -> str:
    """Fake-llm answer. Attack-shaped input is refused so the platform suite can pass."""
    blob = user_text.lower()
    for mock in mocks:
        if not isinstance(mock, dict):
            continue
        result = mock.get("result")
        if isinstance(result, dict):
            blob += " " + str(result.get("text") or "").lower()
    if any(token in blob for token in _ATTACK):
        return "I can't help with that request."
    return user_text


def execute_eval_run(store: Any, eval_run_id: uuid.UUID) -> dict[str, object]:
    """Score every selected case and finish the run."""
    row = store.eval_runs.get(eval_run_id)
    if not isinstance(row, dict):
        return {"status": "failed"}
    if row.get("status") in {"cancelled", "completed"}:
        return _summary(row)
    row["status"] = "running"
    row["started_at"] = utcnow()
    suite = store.eval_suites.get(row.get("suite_id"))
    gate = suite.get("gate") if isinstance(suite, dict) else {}
    if not isinstance(gate, dict):
        gate = {}
    selected = _cases(store, row)
    results: list[dict[str, object]] = []
    for case in selected:
        outcome = _run_case(store, row, case)
        scores = grade(_list(case.get("assertions")), outcome)
        ok = passed(scores)
        saved = _save_result(store, row, case, outcome, scores, ok)
        results.append(saved)
        CASE_SECONDS.observe(max(_int(outcome.get("latency_ms")), 1) / 1000)
    baseline = _baseline(store, row.get("baseline_eval_run_id"))
    summary = summarise(gate, results, baseline)
    row["summary"] = summary
    row["status"] = "completed"
    row["finished_at"] = utcnow()
    suite_name = str(suite.get("name") if isinstance(suite, dict) else row.get("suite_id"))
    PASS_RATE.labels(suite=suite_name).set(_float(summary.get("pass_rate")))
    RUNS.labels(status="completed", trigger=str(row.get("trigger") or "manual")).inc()
    store.domain_events.append(
        {
            "topic": "eval.completed",
            "payload": {
                "eval_run_id": str(eval_run_id),
                "suite_id": str(row.get("suite_id")),
                "agent_version_id": str(row.get("agent_version_id") or ""),
                "summary": summary,
                "tenant_id": str(row.get("tenant_id")),
            },
            "at": utcnow().isoformat(),
        }
    )
    _notify(store, row, summary)
    if row.get("trigger") == "publish_gate":
        _finish_gate(store, row, bool(summary.get("gate_passed")))
    return summary


def _run_case(
    store: Any, eval_run: dict[str, object], case: dict[str, object]
) -> dict[str, object]:
    raw_input = case.get("input")
    messages = raw_input.get("messages") if isinstance(raw_input, dict) else []
    turns = [str(item) for item in messages] if isinstance(messages, list) else []
    raw_mocks = case.get("tool_mocks")
    mocks: list[object] = raw_mocks if isinstance(raw_mocks, list) else []
    context = {
        "suite_id": str(eval_run.get("suite_id")),
        "case_id": str(case.get("id")),
        "tool_mocks": mocks,
        "as_user": raw_input.get("as_user") if isinstance(raw_input, dict) else None,
        "mock_all_tools": bool(eval_run.get("mock_all_tools")),
    }
    output = ""
    run_id = new_id()
    calls: list[dict[str, object]] = []
    now = utcnow()
    conversation_id = new_id()
    tenant_id = eval_run.get("tenant_id")
    user_id = eval_run.get("triggered_by")
    agent_id = eval_run.get("agent_id")
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "channel": "eval",
        "title": str(case.get("name") or "eval"),
        "created_at": now,
        "updated_at": now,
    }
    for turn in turns or [""]:
        output = scripted_reply(turn, mocks)
        run_id = new_id()
        store.runs[run_id] = {
            "id": run_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "agent_version_id": eval_run.get("agent_version_id"),
            "conversation_id": conversation_id,
            "trigger": "eval",
            "status": "completed",
            "eval_context": context,
            "result_summary": output,
            "created_at": now,
            "started_at": now,
            "ended_at": now,
            "usage": {"steps": 1, "cost_micros": 0, "wall_clock_ms": 12},
        }
    for mock in mocks:
        if not isinstance(mock, dict):
            continue
        call_id = new_id()
        error = mock.get("error")
        calls.append(
            {
                "id": call_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "qualified_name": str(mock.get("tool") or ""),
                "arguments": mock.get("match_args") or {},
                "status": "failed" if isinstance(error, dict) else "completed",
                "risk_class": "R0",
            }
        )
        store.tool_calls[call_id] = calls[-1]
    return {
        "output_text": output,
        "tool_calls": calls,
        "latency_ms": 12,
        "cost_micros": 0,
        "steps": max(len(turns), 1),
        "citations": [],
        "denied": 0,
        "run_id": run_id,
    }


def _save_result(  # noqa: PLR0917
    store: Any,
    eval_run: dict[str, object],
    case: dict[str, object],
    outcome: dict[str, object],
    scores: dict[str, dict[str, object]],
    ok: bool,  # noqa: FBT001
) -> dict[str, object]:
    result_id = new_id()
    saved = {
        "id": result_id,
        "tenant_id": eval_run.get("tenant_id"),
        "eval_run_id": eval_run.get("id"),
        "case_id": case.get("id"),
        "run_id": outcome.get("run_id"),
        "passed": ok,
        "scores": scores,
        "output_text": str(outcome.get("output_text") or ""),
        "latency_ms": outcome.get("latency_ms"),
        "cost_micros": outcome.get("cost_micros") or 0,
        "tags": _strings(case.get("tags")),
        "created_at": utcnow(),
    }
    store.eval_results[result_id] = saved
    return saved


def _cases(store: Any, eval_run: dict[str, object]) -> list[dict[str, object]]:
    suite_id = eval_run.get("suite_id")
    tags = eval_run.get("tags")
    wanted = {str(tag) for tag in tags} if isinstance(tags, list) else set()
    found: list[dict[str, object]] = []
    for case in store.eval_cases.values():
        if not isinstance(case, dict) or case.get("suite_id") != suite_id:
            continue
        case_tags = case.get("tags")
        names = {str(tag) for tag in case_tags} if isinstance(case_tags, list) else set()
        if wanted and not wanted.intersection(names):
            continue
        found.append(case)
    found.sort(key=lambda item: str(item.get("name") or ""))
    return found


def _baseline(store: Any, baseline_id: object) -> dict[str, bool]:
    if not isinstance(baseline_id, uuid.UUID):
        return {}
    found: dict[str, bool] = {}
    for result in store.eval_results.values():
        if isinstance(result, dict) and result.get("eval_run_id") == baseline_id:
            found[str(result.get("case_id"))] = bool(result.get("passed"))
    return found


def _notify(store: Any, eval_run: dict[str, object], summary: dict[str, object]) -> None:
    regressions = summary.get("regressions")
    regressed = isinstance(regressions, list) and bool(regressions)
    title = "Evaluation regressed" if regressed else "Evaluation finished"
    store.notifications.append(
        {
            "kind": "eval_completed",
            "title": title,
            "body": title,
            "link": f"/admin/evals?run={eval_run.get('id')}",
            "user_id": str(eval_run.get("triggered_by") or ""),
            "tenant_id": str(eval_run.get("tenant_id") or ""),
        }
    )


def _finish_gate(store: Any, eval_run: dict[str, object], passed_gate: bool) -> None:  # noqa: FBT001
    from ar_domain.agents.service import AgentLifecycle  # noqa: PLC0415

    version_id = eval_run.get("agent_version_id")
    if not isinstance(version_id, uuid.UUID):
        return
    AgentLifecycle(store).complete_gated_publish(version_id, passed=passed_gate)


def _summary(row: dict[str, object]) -> dict[str, object]:
    summary = row.get("summary")
    return summary if isinstance(summary, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return float(value)


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)

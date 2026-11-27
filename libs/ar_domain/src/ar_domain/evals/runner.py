"""Execute one evaluation run on the process store.

Spec: docs/03-specs/18-observability-eval.md §4.2.
"""

import asyncio
import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.evals.metrics import CASE_SECONDS, PASS_RATE, RUNS
from ar_domain.evals.scoring import grade, passed, summarise

if TYPE_CHECKING:
    from typing import Any


async def execute_eval_run(store: Any, eval_run_id: uuid.UUID) -> dict[str, object]:
    """Run every selected case through the agent, score it, and finish the run.

    A failure that is not a case failing ends the run as ``failed``. A run that is the
    gate for a publish then reports that the gate did not pass.
    """
    row = store.eval_runs.get(eval_run_id)
    if not isinstance(row, dict):
        return {"status": "failed"}
    if row.get("status") in {"cancelled", "completed", "failed"}:
        return _summary(row)
    try:
        return await _execute(store, eval_run_id, row)
    except Exception as exc:  # noqa: BLE001 — an eval run must end, and a gate must hear
        from ar_common.logging import get_logger  # noqa: PLC0415
        from ar_domain.tools.logic import raised_at  # noqa: PLC0415

        get_logger(__name__).error(
            "eval_run_failed",
            eval_run_id=str(eval_run_id),
            error_type=type(exc).__name__,
            where=raised_at(exc),
        )
        row["status"] = "failed"
        row["finished_at"] = utcnow()
        RUNS.labels(status="failed", trigger=str(row.get("trigger") or "manual")).inc()
        if row.get("trigger") == "publish_gate":
            _finish_gate(store, row, False)
        return _summary(row)


async def _execute(store: Any, eval_run_id: uuid.UUID, row: dict[str, object]) -> dict[str, object]:
    """In one process: begin, every case several at a time, then finish."""
    case_ids = begin_eval_run(store, eval_run_id)
    gate_keeper = asyncio.Semaphore(_concurrency())

    async def one(case_id: str) -> None:
        async with gate_keeper:
            await score_eval_case(store, eval_run_id, case_id)

    await asyncio.gather(*(one(case_id) for case_id in case_ids))
    del row
    return finish_eval_run(store, eval_run_id)


def begin_eval_run(store: Any, eval_run_id: uuid.UUID) -> list[str]:
    """Mark the run running and return the ids of the cases it scores, in order.

    A run that already ended returns no cases. A workflow scores each case in its own
    activity, so a suite of any size finishes and one slow case never ends the run.
    """
    row = store.eval_runs.get(eval_run_id)
    if not isinstance(row, dict) or row.get("status") in {"cancelled", "completed", "failed"}:
        return []
    if row.get("status") != "running":
        row["status"] = "running"
        row["started_at"] = utcnow()
    return [str(case["id"]) for case in _cases(store, row)]


async def score_eval_case(store: Any, eval_run_id: uuid.UUID, case_id: str) -> bool:
    """Run one case through the agent, judge it and save its result. True when it passed.

    Safe to repeat: a case that already has a result in this run is not run again. A
    case that cannot run is saved as a failed result that says why; it never ends the run.
    """
    row = store.eval_runs.get(eval_run_id)
    case = store.eval_cases.get(_uuid(case_id))
    if not isinstance(row, dict) or not isinstance(case, dict):
        return False
    done = _result_for(store, eval_run_id, case.get("id"))
    if done is not None:
        return bool(done.get("passed"))
    if row.get("status") in {"cancelled", "completed", "failed"}:
        return False
    try:
        outcome = await _run_case(store, row, case)
        scores = grade(_list(case.get("assertions")), outcome)
        await _judge(store, row, case, outcome, scores)
    except Exception as exc:  # noqa: BLE001 - one case that cannot run is a failed case
        from ar_domain.tools.logic import raised_at  # noqa: PLC0415

        end_eval_agent_runs(store, eval_run_id, case_id=str(case.get("id")))
        outcome = {"output_text": "", "latency_ms": 0, "cost_micros": 0}
        scores = {
            "case_error": {
                "passed": False,
                "score": 0.0,
                "verdict": "failed",
                "detail": f"The case did not run: {type(exc).__name__} at {raised_at(exc)}.",
            }
        }
    ok = passed(scores)
    _save_result(store, row, case, outcome, scores, ok)
    CASE_SECONDS.observe(max(_int(outcome.get("latency_ms")), 1) / 1000)
    return ok


def finish_eval_run(store: Any, eval_run_id: uuid.UUID) -> dict[str, object]:
    """Summarise the saved results, end the run and tell whoever waits for it.

    A selected case with no result (its activity never finished) counts as failed.
    """
    row = store.eval_runs.get(eval_run_id)
    if not isinstance(row, dict):
        return {"status": "failed"}
    if row.get("status") in {"cancelled", "completed", "failed"}:
        return _summary(row)
    suite = store.eval_suites.get(row.get("suite_id"))
    gate = suite.get("gate") if isinstance(suite, dict) else {}
    if not isinstance(gate, dict):
        gate = {}
    results: list[dict[str, object]] = []
    for case in _cases(store, row):
        saved = _result_for(store, eval_run_id, case.get("id"))
        if saved is None:
            missing = {
                "case_error": {
                    "passed": False,
                    "score": 0.0,
                    "verdict": "failed",
                    "detail": "The case did not finish.",
                }
            }
            outcome = {"output_text": "", "latency_ms": 0, "cost_micros": 0}
            saved = _save_result(store, row, case, outcome, missing, False)
        results.append(saved)
    end_eval_agent_runs(store, eval_run_id)
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


def fail_eval_run(store: Any, eval_run_id: uuid.UUID, reason: str) -> dict[str, object]:
    """End a run that broke for a reason other than a failing case. A gate hears it."""
    row = store.eval_runs.get(eval_run_id)
    if not isinstance(row, dict):
        return {"status": "failed"}
    if row.get("status") in {"cancelled", "completed", "failed"}:
        return _summary(row)
    from ar_common.logging import get_logger  # noqa: PLC0415

    get_logger(__name__).error("eval_run_failed", eval_run_id=str(eval_run_id), error_type=reason)
    end_eval_agent_runs(store, eval_run_id)
    row["status"] = "failed"
    row["finished_at"] = utcnow()
    RUNS.labels(status="failed", trigger=str(row.get("trigger") or "manual")).inc()
    if row.get("trigger") == "publish_gate":
        _finish_gate(store, row, False)
    return _summary(row)


def end_eval_agent_runs(store: Any, eval_run_id: uuid.UUID, *, case_id: str | None = None) -> int:
    """End the agent runs an eval run (or one of its cases) left working. How many.

    An eval run's agent runs live in the process that scores the case, not in a
    workflow of their own. A case that breaks, or a process that stops, would leave them
    working for ever, and working runs count against the tenant's run limit.
    """
    from ar_domain.conversations.logic import run_is_active  # noqa: PLC0415

    ended = 0
    for run in list(getattr(store, "runs", {}).values()):
        if not isinstance(run, dict) or run.get("trigger") != "eval":
            continue
        context = run.get("eval_context")
        if not isinstance(context, dict) or context.get("eval_run_id") != str(eval_run_id):
            continue
        if case_id is not None and context.get("case_id") != case_id:
            continue
        if not run_is_active(str(run.get("status"))):
            continue
        run["status"] = "failed"
        run["ended_at"] = utcnow()
        run["error"] = {
            "code": "eval_case_ended",
            "message": "The eval case this run belonged to ended before the run did.",
        }
        ended += 1
    return ended


def eval_concurrency() -> int:
    """How many cases of one run are worked on at the same time."""
    return _concurrency()


def _result_for(store: Any, eval_run_id: uuid.UUID, case_id: object) -> dict[str, object] | None:
    for result in store.eval_results.values():
        if (
            isinstance(result, dict)
            and result.get("eval_run_id") == eval_run_id
            and result.get("case_id") == case_id
        ):
            return result
    return None


def _concurrency() -> int:
    """``AR_EVAL_CONCURRENCY``: cases of one run worked on at the same time."""
    from ar_common.settings import get_settings  # noqa: PLC0415

    return max(1, int(get_settings().eval_concurrency))


async def _judge(
    store: Any,
    eval_run: dict[str, object],
    case: dict[str, object],
    outcome: dict[str, object],
    scores: dict[str, dict[str, object]],
) -> None:
    """Replace each ``llm_judge`` placeholder with the judge model's verdict."""
    assertions = _list(case.get("assertions"))
    pending = []
    for key in scores:
        position = key.removeprefix("llm_judge_")
        if key.startswith("llm_judge_") and position.isdigit() and int(position) < len(assertions):
            pending.append((key, assertions[int(position)]))
    if not pending:
        return
    status = str(outcome.get("status") or "")
    if status and status != "completed":
        # No answer to judge: the agent's run itself did not complete. Say so, and do not
        # spend judge calls on an empty answer.
        for key, _item in pending:
            scores[key] = {
                "passed": False,
                "score": 0.0,
                "verdict": "failed",
                "detail": f"The agent's run ended {status}, so the answer was not judged.",
            }
        return
    from ar_common.offload import run_sync  # noqa: PLC0415
    from ar_domain.evals.judge import judge_case  # noqa: PLC0415

    raw_input = case.get("input")
    messages = raw_input.get("messages") if isinstance(raw_input, dict) else []
    turns = [str(item) for item in messages] if isinstance(messages, list) else []
    question = "\n".join(turns)
    for key, item in pending:
        scores[key] = await run_sync(
            judge_case,
            store,
            eval_run.get("tenant_id"),
            item if isinstance(item, dict) else {},
            outcome,
            question,
        )


async def _run_case(
    store: Any, eval_run: dict[str, object], case: dict[str, object]
) -> dict[str, object]:
    """Post each user turn of the case to the agent and collect what the runs did."""
    raw_input = case.get("input")
    messages = raw_input.get("messages") if isinstance(raw_input, dict) else []
    turns = [str(item) for item in messages] if isinstance(messages, list) else []
    raw_mocks = case.get("tool_mocks")
    mocks: list[object] = raw_mocks if isinstance(raw_mocks, list) else []
    context = {
        "eval_run_id": str(eval_run.get("id")),
        "suite_id": str(eval_run.get("suite_id")),
        "case_id": str(case.get("id")),
        "tool_mocks": mocks,
        "as_user": raw_input.get("as_user") if isinstance(raw_input, dict) else None,
        "mock_all_tools": bool(eval_run.get("mock_all_tools")),
    }
    tenant_id = _uuid(eval_run.get("tenant_id"))
    user_id = _uuid(eval_run.get("triggered_by"))
    agent_id = _uuid(eval_run.get("agent_id"))
    override = eval_run.get("model_alias_override")
    version_id = eval_run.get("agent_version_id")
    conversation_id = _open(store, tenant_id, user_id, agent_id, version_id)
    conversation = store.conversations[conversation_id]
    conversation["channel"] = "eval"
    conversation["title"] = str(case.get("name") or "eval")
    if override:
        conversation["model_alias"] = str(override)
    run_ids: list[uuid.UUID] = []
    for turn in turns or [""]:
        posted = store.post_message(tenant_id, user_id, conversation_id, turn, schedule=False)
        run_id = _uuid(posted["run"]["id"])
        run = store.runs[run_id]
        run["trigger"] = "eval"
        run["eval_context"] = context
        if isinstance(version_id, uuid.UUID):
            run["agent_version_id"] = version_id
        run_ids.append(run_id)
        await store.generate(run_id, turn, [])
        if str(run.get("status")) != "completed":
            break
    return _outcome(store, run_ids, raw_input)


def _open(
    store: Any,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    version_id: object,
) -> uuid.UUID:
    """Open the conversation a case runs in, on the version under evaluation.

    A gate scores a draft, which cannot start an ordinary conversation, so the case
    uses the preview conversation a builder uses to try a draft. Starting the eval run
    was authorised already; this actor only reaches that agent version.
    """
    if not isinstance(version_id, uuid.UUID):
        return _uuid(store.create_conversation(tenant_id, user_id, agent_id)["id"])
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.agents.service import AgentLifecycle  # noqa: PLC0415

    actor = Actor(
        tenant_id=tenant_id, user_id=user_id, permissions=frozenset({"agents:manage_all"})
    )
    return _uuid(AgentLifecycle(store).open_preview(actor, version_id)["id"])


def _outcome(store: Any, run_ids: list[uuid.UUID], raw_input: object) -> dict[str, object]:
    """What the graders read: the last answer, every tool call, and the usage of the runs."""
    last = store.runs[run_ids[-1]]
    assistant = store.messages.get(last.get("assistant_message_id"))
    answer = str(assistant.get("text") or "") if isinstance(assistant, dict) else ""
    content = assistant.get("content") if isinstance(assistant, dict) else None
    citations = [
        part
        for part in (content if isinstance(content, list) else [])
        if isinstance(part, dict) and part.get("type") == "citation"
    ]
    calls = [
        row
        for row in list(store.tool_calls.values())
        if isinstance(row, dict) and row.get("run_id") in run_ids
    ]
    latency = 0
    cost = 0
    steps = 0
    for run_id in run_ids:
        run = store.runs[run_id]
        usage = run.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        cost += _int(usage.get("cost_micros"))
        steps += max(_int(usage.get("steps")), 1)
        started, ended = run.get("started_at") or run.get("created_at"), run.get("ended_at")
        if started is not None and ended is not None:
            latency += max(int((ended - started).total_seconds() * 1000), 0)
    return {
        "output_text": answer,
        "status": str(last.get("status") or ""),
        "tool_calls": calls,
        "latency_ms": latency,
        "cost_micros": cost,
        "steps": steps,
        "citations": citations,
        "denied": sum(1 for row in calls if row.get("status") == "denied"),
        "run_id": run_ids[-1],
        "grounding": _grounding_report(raw_input),
    }


def _uuid(value: object) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _grounding_report(raw_input: object) -> dict[str, object]:
    if isinstance(raw_input, dict) and isinstance(raw_input.get("grounding"), dict):
        report = raw_input["grounding"]
        return {
            "claims": int(str(report.get("claims") or 0)),
            "grounded_claims": int(str(report.get("grounded_claims") or 0)),
            "mode": str(report.get("mode") or "strict"),
        }
    return {"claims": 1, "grounded_claims": 1, "mode": "strict"}


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

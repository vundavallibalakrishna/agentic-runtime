"""A call to other agents on the worker, where each called agent is its own run workflow.

A step that reaches ``agents_call``, ``agents_parallel`` or ``agents_handoff`` does not run
the agents itself. ``begin`` creates their runs, notes the call on the caller's checkpoint
and hands the caller's workflow what to start. The workflow starts one ``AgentRunWorkflow``
for each and waits. The caller's next step comes back to the same tool call, and ``finish``
reads how each run ended and answers the call.

So a called agent survives a worker restart, waits for a person like any run, and is not
bound by the length of its caller's step. Nothing about the call is kept in process memory.
"""

from __future__ import annotations

import uuid
from typing import Any  # noqa: TC003

from ar_domain.orchestration import events
from ar_domain.orchestration.children import (
    _TIMEOUT_MESSAGE,
    call_error,
    definition_of,
    finish_failed,
    note_step,
    open_child,
    open_reply,
    refusal,
    remaining_budget,
    roll,
    told,
    too_many,
)
from ar_domain.orchestration.spec import brief, subagent_spec, whole
from ar_domain.orchestration.spend import spent_so_far
from ar_domain.runs.request import ask

KEY = "agent_call"
_ENDED = frozenset({"completed", "failed", "cancelled", "budget_exceeded"})


def open_call(run: dict[str, object], call_id: str) -> dict[str, object] | None:
    """The call this run is waiting on, when it is this tool call."""
    checkpoint = run.get("checkpoint")
    saved = checkpoint.get(KEY) if isinstance(checkpoint, dict) else None
    if isinstance(saved, dict) and str(saved.get("call_id")) == call_id:
        return saved
    return None


def _note(run: dict[str, object], saved: dict[str, object] | None) -> None:
    raw = run.get("checkpoint")
    checkpoint = dict(raw) if isinstance(raw, dict) else {}
    if saved is None:
        checkpoint.pop(KEY, None)
    else:
        checkpoint[KEY] = saved
    run["checkpoint"] = checkpoint


def _asked_for(
    name: str, payload: dict[str, object], limit: int
) -> tuple[list[dict[str, object]], int]:
    """The agents one call names with their tasks, and how many were over the limit."""
    if name != "agents_parallel":
        task = str(payload.get("task") or payload.get("note") or "")
        single = {"agent": str(payload.get("agent") or ""), "task": task}
        return [{**single, "input": payload.get("input")}], 0
    calls = payload.get("calls")
    rows = [item for item in calls if isinstance(item, dict)] if isinstance(calls, list) else []
    chosen: list[dict[str, object]] = [
        {
            "agent": str(item.get("agent") or ""),
            "task": str(item.get("task") or ""),
            "input": item.get("input"),
        }
        for item in rows[:limit]
    ]
    return chosen, len(rows) - len(chosen)


def begin(
    store: Any, run: dict[str, object], call: dict[str, object], state: dict[str, object]
) -> list[dict[str, object]]:
    """Create the run of each agent the call names. Return what the workflow starts.

    An agent that cannot be called is noted with its reason and starts nothing. An empty
    list means there is nothing to wait for, and the call can be answered at once.
    """
    from ar_domain.runs.dispatch import workflow_payload  # noqa: PLC0415

    name = str(call.get("name") or "")
    call_id = str(call.get("id") or "call")
    arguments = call.get("arguments")
    spec = subagent_spec(definition_of(store, run))
    rows, overflow = _asked_for(
        name, arguments if isinstance(arguments, dict) else {}, spec["max_calls"]
    )
    limits = state.get("limits")
    left = remaining_budget(limits if isinstance(limits, dict) else {}, state) if limits else {}
    # The agents of one call draw on what the caller has left now. Each run reads what the
    # others have saved as spent, so the pool holds across workers.
    pool = {
        "call": call_id,
        "tokens": whole(left.get("max_tokens"), 0),
        "cost": whole(left.get("max_cost_micros"), 0),
    }
    items: list[dict[str, object]] = []
    starts: list[dict[str, object]] = []
    for row in rows:
        given = row.get("input")
        slug, refused = refusal(store, run, str(row["agent"]), state, given)
        # The task as the caller wrote it is what a person is shown. The called agent's
        # message carries the input with it.
        task = str(row["task"])
        child = (
            refused
            if refused is not None
            else open_child(store, run, slug, brief(task, given), state)
        )
        if child.get("failed"):
            items.append(
                {"slug": slug, "task": task, "code": child.get("code"), "text": child.get("text")}
            )
            continue
        budget = dict(left)
        # Its time is its own working time, and never more than the caller has left.
        budget["max_wall_clock_s"] = min(
            spec["child_timeout_s"], max(1, whole(left.get("max_wall_clock_s"), 1))
        )
        child["budget_override"] = budget
        ask(child, "budget", budget)
        ask(child, "pool", pool)
        ask(child, "waits", True)
        child["status"] = "queued"
        open_reply(store, child)
        store._emit(run, "subagent.started", events.started(child, task, call_id))
        note_step(
            store,
            run,
            "subagent",
            {"child_run_id": str(child["id"]), "agent": slug, "status": "running"},
        )
        items.append(
            {
                "slug": slug,
                "name": str(child.get("agent_name") or ""),
                "task": task,
                "child_id": str(child["id"]),
            }
        )
        starts.append(workflow_payload(store, child, uuid.UUID(str(child["id"])), task))
    if overflow:
        extra = too_many(overflow, spec["max_calls"])
        items.append({"slug": "", "task": "", "code": extra["code"], "text": extra["text"]})
    _note(run, {"call_id": call_id, "name": name, "items": items})
    # The workflow runs this many at once and starts the next as each one ends.
    run["agent_parallel"] = spec["max_parallel"]
    return starts


def finish(
    store: Any, run: dict[str, object], call: dict[str, object], saved: dict[str, object]
) -> dict[str, object]:
    """Answer the call from how each called agent's run ended."""
    from ar_domain.orchestration.engine import conclude  # noqa: PLC0415

    call_id = str(call.get("id") or "call")
    raw = saved.get("items")
    items = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    outcomes: list[dict[str, object]] = []
    tokens = cost = 0
    for item in items:
        slug = str(item.get("slug") or "")
        if not item.get("child_id"):
            outcomes.append(
                call_error(slug, str(item.get("code") or ""), str(item.get("text") or ""))
            )
            continue
        child = store.runs.get(uuid.UUID(str(item["child_id"])))
        if not isinstance(child, dict):
            outcomes.append(call_error(slug, "child_missing", "This agent's run was not found."))
            continue
        outcome = _ended(store, child, slug, str(item.get("name") or ""))
        spent = spent_so_far(child)
        tokens += spent[0]
        cost += spent[1]
        roll(run, outcome)
        told(
            store,
            run,
            child,
            status=str(outcome["status"]),
            summary=str(outcome.get("text") or ""),
            call_id=call_id,
        )
        outcomes.append(outcome)
    _note(run, None)
    tasks = [str(item.get("task") or "") for item in items]
    return conclude(
        str(saved.get("name") or ""), call_id, outcomes, tasks, tokens=tokens, cost=cost
    )


def _ended(store: Any, child: dict[str, object], slug: str, name: str) -> dict[str, object]:
    """One called agent's result. A run that never ended is closed here, as failed."""
    status = str(child.get("status") or "")
    code = ""
    if status not in _ENDED:
        finish_failed(store, child, "child_not_finished", "This agent did not finish its work.")
        status, code = "failed", "child_not_finished"
    text = str(child.get("result_summary") or _reply_text(store, child))
    error = child.get("error")
    if status != "completed" and isinstance(error, dict) and error.get("message"):
        text = str(error["message"])
        code = code or str(error.get("code") or "")
    if status == "budget_exceeded" and _out_of_time(store, child):
        text, code = _TIMEOUT_MESSAGE, "child_timeout"
    usage = child.get("usage")
    used = usage if isinstance(usage, dict) else {}
    return {
        "status": status,
        "agent": slug,
        "name": name,
        "child_id": str(child.get("id")),
        "tokens_in": whole(used.get("tokens_in"), 0),
        "tokens_out": whole(used.get("tokens_out"), 0),
        "cost": whole(used.get("cost_micros"), 0),
        "failed": status != "completed",
        "code": code,
        "text": text,
    }


def _reply_text(store: Any, child: dict[str, object]) -> str:
    for row in store.messages.values():
        if row.get("run_id") == child.get("id") and row.get("role") == "assistant":
            return str(row.get("text") or "")
    return ""


def _out_of_time(store: Any, child: dict[str, object]) -> bool:
    """Whether the limit that stopped this run was its time."""
    sent = store.events.get(uuid.UUID(str(child.get("id"))), [])
    for event in reversed(sent):
        if event.get("type") == "run.budget_exceeded":
            data = event.get("data")
            return isinstance(data, dict) and data.get("limit") == "max_wall_clock_s"
    return False


async def step(store: Any, run: dict[str, object]) -> None:
    """One step of a called agent's own run, on the worker.

    It is the agent the call named, with the task as its message, and none of what a
    person's turn sets up: no conversation history, no title, nothing remembered after.
    """
    from ar_domain.tools.agent_loop import model_alias_for, run_agent_loop  # noqa: PLC0415

    assistant = store.messages.get(run.get("assistant_message_id"))
    source = store.messages.get(run.get("input_message_id"))
    task = str(source.get("text") or "") if isinstance(source, dict) else ""
    ready = store._completion_call(uuid.UUID(str(run["tenant_id"])), model_alias_for(store, run))
    if not isinstance(assistant, dict) or ready is None:
        finish_failed(store, run, "model_unavailable", "This agent has no model to run.")
        return
    if str(run.get("status")) == "queued":
        run["status"] = "running"
        store._emit(run, "run.started", {"model_alias": model_alias_for(store, run)})
    if not await run_agent_loop(store, run, assistant, task, one_step=True):
        finish_failed(store, run, "model_unavailable", "This agent has no model to run.")

"""Child runs: one agent, several in parallel, handoff, timeout and budget roll-up."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any  # noqa: TC003

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_common.wrapping import wrap_tool_result
from ar_domain.orchestration import events
from ar_domain.orchestration.spec import chain, depth_blocked, is_cycle, subagent_spec, whole
from ar_domain.orchestration.spend import Spend, meter, release, spend_of
from ar_domain.runs.request import ask
from ar_domain.skills.delegate import _insert_child
from ar_domain.tools.agent_loop import _flush_run, model_alias_for

_TIMEOUT_MESSAGE = "The child timed out and was not retried. The parent can continue or stop."
_LIVE = frozenset({"queued", "running", "waiting_approval", "waiting_input"})


def definition_of(store: Any, run: dict[str, object]) -> dict[str, object]:
    version = store.versions.get(run.get("agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    return definition if isinstance(definition, dict) else {}


def remaining_budget(limits: dict[str, int], state: dict[str, object]) -> dict[str, int]:
    elapsed = whole(state.get("elapsed_s"), 0)
    return {
        "max_steps": max(0, limits["max_steps"] - whole(state.get("steps"), 0)),
        "max_tokens": max(0, limits["max_tokens"] - whole(state.get("tokens"), 0)),
        "max_cost_micros": max(0, limits["max_cost_micros"] - whole(state.get("cost"), 0)),
        "max_wall_clock_s": max(0, limits["max_wall_clock_s"] - elapsed),
        "max_tool_calls": max(0, limits["max_tool_calls"] - whole(state.get("used_calls"), 0)),
    }


def budget_left(limits: dict[str, int], state: dict[str, object]) -> str | None:
    left = remaining_budget(limits, state)
    for key, value in left.items():
        if value <= 0:
            return key
    return None


async def run_named(
    store: Any,
    parent: dict[str, object],
    slug: str,
    task: str,
    state: dict[str, object],
) -> dict[str, object]:
    """Run one child. A timeout, cycle, depth or budget failure is a tool error, not a crash."""
    spec = subagent_spec(definition_of(store, parent))
    allowed = set(spec["allowed"])
    current = chain(parent)
    self_name = current[-1] if current else ""
    if slug == "self":
        slug = self_name
    permitted = slug in allowed or (slug == self_name and spec["allow_self_clone"] is True)
    if not permitted:
        return _error(slug, "not_allowed", f"{slug} is not an agent this one can call.")
    if is_cycle(parent, slug, allow_self=spec["allow_self_clone"] is True):
        return _error(
            slug, "cycle", f"Calling {slug} would loop back to an agent already in this run."
        )
    if depth_blocked(parent, spec["max_depth"]):
        return _error(slug, "depth_exceeded", "This run is already at the depth limit.")
    limits = state.get("limits")
    budget = limits if isinstance(limits, dict) else {}
    blocked = budget_left(budget, state)
    if blocked:
        label = blocked.replace("_", " ")
        return _error(slug, "budget_exceeded", f"Stopped because the {label} limit was reached.")
    left = remaining_budget(budget, state)["max_wall_clock_s"]
    timeout = min(spec["child_timeout_s"], max(1, left))
    # Which child this call started. Each call keeps its own note: several run at once,
    # and a shared one let a timeout be pinned on a sibling that was still working.
    holder: dict[str, object] = {}
    try:
        return await asyncio.wait_for(
            _drive(store, parent, slug, task, state, holder=holder), timeout=timeout
        )
    except TimeoutError:
        child = holder.get("child")
        cut_short: dict[str, object] = {}
        # Giving up on the child cancels it. What ended it was its time, and it says so.
        if isinstance(child, dict) and str(child.get("status")) in {*_LIVE, "cancelled"}:
            _finish_failed(store, child, "child_timeout", _TIMEOUT_MESSAGE)
            _roll(parent, _spent(child, "failed"))
            _told(
                store,
                parent,
                child,
                status="failed",
                summary=_TIMEOUT_MESSAGE,
                call_id=str(state.get("call_id") or ""),
            )
            await _flush_run(store)
            # The answer names the run that was cut short, so a person can open it.
            cut_short = _named(child)
        return {**_error(slug, "child_timeout", _TIMEOUT_MESSAGE), **cut_short}
    finally:
        started = holder.get("child")
        if isinstance(started, dict):
            release(started)


def pool_for(state: dict[str, object]) -> Spend:
    """The pool the agents in one call draw on: what the caller has left when it calls."""
    found = state.get("pool")
    if isinstance(found, Spend):
        return found
    limits = state.get("limits")
    left = remaining_budget(limits if isinstance(limits, dict) else {}, state) if limits else {}
    pool = Spend(left.get("max_tokens", 0), left.get("max_cost_micros", 0))
    state["pool"] = pool
    return pool


async def run_parallel(
    store: Any,
    parent: dict[str, object],
    calls: list[dict[str, object]],
    state: dict[str, object],
) -> dict[str, object]:
    spec = subagent_spec(definition_of(store, parent))
    cap = spec["max_parallel"]
    pool_for(state)
    chosen = [item for item in calls if isinstance(item, dict)][:cap]
    overflow = len(calls) - len(chosen)
    results = await asyncio.gather(
        *[
            run_named(
                store, parent, str(item.get("agent") or ""), str(item.get("task") or ""), state
            )
            for item in chosen
        ]
    )
    if overflow:
        results = [
            *results,
            _error(
                "",
                "fanout",
                f"{overflow} calls were not started because the fan-out limit is {cap}.",
            ),
        ]
    failed = any(item.get("failed") for item in results)
    return {"failed": failed, "results": list(results)}


async def _drive(
    store: Any,
    parent: dict[str, object],
    slug: str,
    task: str,
    state: dict[str, object],
    *,
    holder: dict[str, object],
) -> dict[str, object]:
    from ar_domain.skills.delegate import plan_child  # noqa: PLC0415

    spec = subagent_spec(definition_of(store, parent))
    limits = state.get("limits")
    budget = limits if isinstance(limits, dict) else {}
    allowed = [str(item) for item in spec["allowed"]]
    if spec["allow_self_clone"] is True and slug not in allowed:
        allowed.append(slug)
    planned = plan_child(
        {
            "run_id": str(parent.get("id")),
            "depth": whole(parent.get("depth"), 0),
            "max_depth": spec["max_depth"],
            "remaining_budget": remaining_budget(budget, state),
            "allowed": allowed,
            "allow_self_clone": spec["allow_self_clone"],
            "agent": slug,
            "task": task,
            "index": whole(state.get("used_calls"), 0),
        }
    )
    if planned.get("error"):
        return _error(slug, str(planned["error"]), str(planned["error"]))
    inserted = _insert_child(store, parent, planned, {"agent": slug, "task": task})
    stored = store.runs.get(inserted.get("id"))
    child = stored if isinstance(stored, dict) else inserted
    child["agent_chain"] = [*chain(parent), slug]
    child["budget_override"] = remaining_budget(budget, state)
    ask(child, "orchestration_child", True)
    meter(child, pool_for(state))
    holder["child"] = child
    child["workspace_ref"] = f"workspace:{child['id']}"
    # The child is saved as soon as it exists, not when the parent's step ends. Other
    # processes then see it: the screen that draws the run, a stop from the person, and
    # the tool gateway, which records an approval request against the child's run.
    await _flush_run(store)
    call_id = str(state.get("call_id") or "")
    _emit(store, parent, "subagent.started", events.started(child, task, call_id))
    _step(
        store,
        parent,
        "subagent",
        {"child_run_id": str(child["id"]), "agent": slug, "status": "running"},
    )
    try:
        outcome = await _complete(store, child, task)
    except asyncio.CancelledError:
        # The parent was stopped, or gave up waiting. The child ends with it.
        if str(child.get("status")) in _LIVE:
            _end(store, child, "cancelled")
        await asyncio.shield(_flush_run(store))
        raise
    await _flush_run(store)
    _told(
        store,
        parent,
        child,
        status=str(outcome["status"]),
        summary=str(outcome.get("text") or ""),
        call_id=call_id,
    )
    _roll(parent, outcome)
    return outcome


async def _complete(store: Any, child: dict[str, object], task: str) -> dict[str, object]:
    alias_target = store._completion_call(
        uuid.UUID(str(child["tenant_id"])), model_alias_for(store, child)
    )
    if not alias_target[3]:
        return _finish_failed(store, child, "model_unavailable", "This agent has no model to run.")
    assistant = _assistant(store, child)
    from ar_domain.tools.agent_loop import run_agent_loop  # noqa: PLC0415

    ran = await run_agent_loop(store, child, assistant, task)
    if not ran:
        return _finish_failed(store, child, "model_unavailable", "This agent has no model to run.")
    status = str(child.get("status") or "completed")
    if status in {"waiting_input", "waiting_approval"}:
        # A called agent has nobody to wait for: the person is talking to the agent that
        # called it. Its question used to come back as if it were the answer.
        return _finish_failed(
            store,
            child,
            "child_needs_a_person",
            "This agent stopped to ask a person, which an agent called by another cannot "
            "do. Ask the person yourself, then call it again with what it needs.",
        )
    failed = status in {"failed", "budget_exceeded", "cancelled"}
    text = str(child.get("result_summary") or assistant.get("text") or "")
    error = child.get("error")
    if failed and isinstance(error, dict):
        text = str(error.get("message") or text)
    return {**_spent(child, status), "failed": failed, "text": text}


def _named(child: dict[str, object]) -> dict[str, object]:
    return {"name": child.get("agent_name") or "", "child_id": str(child.get("id"))}


def _told(
    store: Any,
    parent: dict[str, object],
    child: dict[str, object],
    *,
    status: str,
    summary: str,
    call_id: str,
) -> None:
    spent = _spent(child, status)
    usage = {
        "tokens_in": spent["tokens_in"],
        "tokens_out": spent["tokens_out"],
        "cost_micros": spent["cost"],
    }
    _emit(
        store,
        parent,
        "subagent.completed",
        events.completed(child, status, summary, usage, call_id),
    )


def _spent(child: dict[str, object], status: str) -> dict[str, object]:
    """What one called agent used, for the caller's totals. Works for one cut short."""
    raw_usage = child.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    own = spend_of(child)
    return {
        "status": status,
        "agent": child.get("agent_slug") or "",
        **_named(child),
        # A run cut short has not written its usage: its own count stands in.
        "tokens_in": whole(usage.get("tokens_in"), 0) or (0 if own is None else own.tokens_in),
        "tokens_out": whole(usage.get("tokens_out"), 0) or (0 if own is None else own.tokens_out),
        "cost": whole(usage.get("cost_micros"), 0) or (0 if own is None else own.cost),
    }


def _assistant(store: Any, child: dict[str, object]) -> dict[str, object]:
    assistant_id = new_id()
    row = {
        "id": assistant_id,
        "tenant_id": child.get("tenant_id"),
        "conversation_id": child.get("conversation_id"),
        "run_id": child.get("id"),
        "parent_message_id": child.get("input_message_id"),
        "role": "assistant",
        "content": [{"type": "text", "text": ""}],
        "text": "",
        "status": "streaming",
        "scope": "run",
        "is_active_branch": False,
        "created_at": utcnow(),
    }
    store.messages[assistant_id] = row
    child["assistant_message_id"] = assistant_id
    stored = store.messages.get(assistant_id)
    return stored if isinstance(stored, dict) else row


def _finish_failed(
    store: Any, child: dict[str, object], code: str, message: str
) -> dict[str, object]:
    child["error"] = {"code": code, "message": message}
    child["result_summary"] = message
    _end(store, child, "failed")
    _emit(store, child, "run.failed", {"error": child["error"]})
    return {**_spent(child, "failed"), "failed": True, "text": message}


def _end(store: Any, child: dict[str, object], status: str) -> None:
    """Close a child that will not finish on its own, and the reply it had started."""
    child["status"] = status
    child["ended_at"] = utcnow()
    reply = store.messages.get(child.get("assistant_message_id"))
    if isinstance(reply, dict) and reply.get("status") == "streaming":
        reply["status"] = status


def _error(slug: str, code: str, message: str) -> dict[str, object]:
    return {
        "failed": True,
        "status": "failed",
        "agent": slug,
        "code": code,
        "text": message,
        "child_id": "",
    }


SUBAGENT_USAGE = "subagents"


def _roll(parent: dict[str, object], outcome: dict[str, object]) -> None:
    """Add one called agent's use to the caller's record, under its own heading.

    The caller's own tokens stay its own. What the agents it called used is kept beside
    them, so the two can be told apart and neither is counted twice.
    """
    usage = parent.get("usage")
    if not isinstance(usage, dict):
        usage = {}
        parent["usage"] = usage
    found = usage.get(SUBAGENT_USAGE)
    called = dict(found) if isinstance(found, dict) else {}
    called["runs"] = whole(called.get("runs"), 0) + 1
    for key, source in (
        ("tokens_in", "tokens_in"),
        ("tokens_out", "tokens_out"),
        ("cost_micros", "cost"),
    ):
        called[key] = whole(called.get(key), 0) + whole(outcome.get(source), 0)
    usage[SUBAGENT_USAGE] = called


def _emit(store: Any, run: dict[str, object], event_type: str, data: dict[str, object]) -> None:
    emit = getattr(store, "_emit", None)
    if callable(emit):
        emit(run, event_type, data)


def _step(store: Any, run: dict[str, object], kind: str, detail: dict[str, object]) -> None:
    steps = getattr(store, "steps", None)
    if not isinstance(steps, dict):
        return
    step_id = new_id()
    steps[step_id] = {
        "id": step_id,
        "tenant_id": run.get("tenant_id"),
        "run_id": run.get("id"),
        "kind": kind,
        "detail": detail,
        "status": detail.get("status") or "running",
    }


def wrapped(name: str, call_id: str, payload: object) -> str:
    import orjson  # noqa: PLC0415

    text = payload if isinstance(payload, str) else orjson.dumps(payload).decode()
    return wrap_tool_result(tool=name, call_id=call_id, content=text or "empty")

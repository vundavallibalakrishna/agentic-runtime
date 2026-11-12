"""Child runs: one agent, several in parallel, handoff, timeout and budget roll-up."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any  # noqa: TC003

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_common.wrapping import wrap_tool_result
from ar_domain.orchestration.spec import chain, depth_blocked, is_cycle, subagent_spec, whole
from ar_domain.runs.request import ask
from ar_domain.skills.delegate import _insert_child
from ar_domain.tools.agent_loop import model_alias_for

_TIMEOUT_MESSAGE = "The child timed out and was not retried. The parent can continue or stop."


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
    state["holder"] = {}
    try:
        return await asyncio.wait_for(_drive(store, parent, slug, task, state), timeout=timeout)
    except TimeoutError:
        holder = state.get("holder")
        child = holder.get("child") if isinstance(holder, dict) else None
        if isinstance(child, dict) and str(child.get("status")) in {"queued", "running"}:
            _finish_failed(store, child, "child_timeout", _TIMEOUT_MESSAGE)
        return _error(slug, "child_timeout", _TIMEOUT_MESSAGE)


async def run_parallel(
    store: Any,
    parent: dict[str, object],
    calls: list[dict[str, object]],
    state: dict[str, object],
) -> dict[str, object]:
    spec = subagent_spec(definition_of(store, parent))
    cap = spec["max_parallel"]
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
    return {
        "failed": failed,
        "results": list(results),
        "tokens": _sum(results, "tokens"),
        "cost": _sum(results, "cost"),
    }


def _sum(rows: list[dict[str, object]], key: str) -> int:
    return sum(whole(row.get(key), 0) for row in rows)


async def _drive(
    store: Any,
    parent: dict[str, object],
    slug: str,
    task: str,
    state: dict[str, object],
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
    holder = state.get("holder")
    if isinstance(holder, dict):
        holder["child"] = child
    child["workspace_ref"] = f"workspace:{child['id']}"
    _emit(store, parent, "subagent.started", {"child_run_id": str(child["id"]), "agent": slug})
    _step(
        store,
        parent,
        "subagent",
        {"child_run_id": str(child["id"]), "agent": slug, "status": "running"},
    )
    outcome = await _complete(store, child, task)
    _emit(
        store,
        parent,
        "subagent.completed",
        {"child_run_id": str(child["id"]), "agent": slug, "status": outcome["status"]},
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
    failed = status in {"failed", "budget_exceeded", "cancelled"}
    raw_usage = child.get("usage")
    usage = raw_usage if isinstance(raw_usage, dict) else {}
    text = str(child.get("result_summary") or assistant.get("text") or "")
    error = child.get("error")
    if failed and isinstance(error, dict):
        text = str(error.get("message") or text)
    return {
        "failed": failed,
        "status": status,
        "agent": child.get("agent_slug") or "",
        "text": text,
        "child_id": str(child.get("id")),
        "tokens": whole(usage.get("tokens_in"), 0) + whole(usage.get("tokens_out"), 0),
        "cost": whole(usage.get("cost_micros"), 0) or whole(usage.get("tokens_out"), 0),
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
    child["status"] = "failed"
    child["ended_at"] = utcnow()
    child["error"] = {"code": code, "message": message}
    child["result_summary"] = message
    _emit(store, child, "run.failed", {"error": child["error"]})
    return {
        "failed": True,
        "status": "failed",
        "agent": str(child.get("agent_slug") or ""),
        "text": message,
        "child_id": str(child.get("id")),
        "tokens": 0,
        "cost": 0,
    }


def _error(slug: str, code: str, message: str) -> dict[str, object]:
    return {
        "failed": True,
        "status": "failed",
        "agent": slug,
        "code": code,
        "text": message,
        "child_id": "",
        "tokens": 0,
        "cost": 0,
    }


def _roll(parent: dict[str, object], outcome: dict[str, object]) -> None:
    usage = parent.get("usage")
    if not isinstance(usage, dict):
        usage = {}
        parent["usage"] = usage
    usage["tokens_in"] = whole(usage.get("tokens_in"), 0) + whole(outcome.get("tokens"), 0)
    usage["cost_micros"] = whole(usage.get("cost_micros"), 0) + whole(outcome.get("cost"), 0)
    usage["tokens_out"] = whole(usage.get("tokens_out"), 0) + whole(outcome.get("cost"), 0)


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

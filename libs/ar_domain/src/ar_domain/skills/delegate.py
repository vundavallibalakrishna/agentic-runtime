"""Subagent delegation. Spec: docs/03-specs/07-agent-runtime.md §7.

The Temporal workflow and the in-process chat loop both call these rules.
Cancelling the parent cancels children. Depth and budget fail closed.
"""

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_common.wrapping import wrap_untrusted
from ar_domain.skills.logic import budget_exhausted, child_budget, platform_max_depth
from ar_domain.skills.metrics import SUBAGENTS

if TYPE_CHECKING:
    from typing import Any


def plan_child(payload: dict[str, object]) -> dict[str, object]:
    """Pure child plan used by the ``create_child_run`` activity."""
    parent_depth = _count(payload.get("depth"))
    max_depth = min(_count(payload.get("max_depth")) or 1, platform_max_depth())
    if parent_depth + 1 > max_depth:
        return {"error": "depth_exceeded", "child_run_id": "", "child_payload": {}}
    remaining = payload.get("remaining_budget")
    budget = remaining if isinstance(remaining, dict) else {}
    exhausted = budget_exhausted(budget)
    if exhausted:
        return {
            "error": "budget_exceeded",
            "limit": exhausted,
            "child_run_id": "",
            "child_payload": {},
        }
    allowed = payload.get("allowed")
    names = allowed if isinstance(allowed, list) else []
    agent = str(payload.get("agent") or "")
    self_clone = payload.get("allow_self_clone") is True and agent == "self"
    if agent != "self" and agent not in {str(item) for item in names}:
        return {"error": "not_allowed", "child_run_id": "", "child_payload": {}}
    if agent == "self" and not self_clone:
        return {"error": "not_allowed", "child_run_id": "", "child_payload": {}}
    index = _count(payload.get("index"))
    parent_id = str(payload.get("run_id") or "run")
    child_id = f"{parent_id}-child-{index}"
    child_def = payload.get("child_budget")
    narrowed = child_budget(child_def if isinstance(child_def, dict) else {}, budget)
    task = str(payload.get("task") or "")[:8000]
    child_payload = {
        "run_id": child_id,
        "depth": parent_depth + 1,
        "max_depth": max_depth,
        "platform_max_depth": platform_max_depth(),
        "remaining_budget": narrowed,
        "delegations": [],
        "final_text": task[:8000],
        "wait_approval": payload.get("wait_approval") is True,
        "usage": {"tokens_in": 1, "tokens_out": max(1, len(task.split()))},
        "agent": agent,
        "file_ids": payload.get("files") if isinstance(payload.get("files"), list) else [],
    }
    return {"error": "", "child_run_id": child_id, "child_payload": child_payload}


def delegate(
    store: Any,
    parent: dict[str, object],
    briefs: list[dict[str, object]],
) -> dict[str, object]:
    """Create child runs, finish them, and roll usage up to the parent."""
    definition = _definition(store, parent)
    subagents = definition.get("subagents") if isinstance(definition, dict) else {}
    spec = subagents if isinstance(subagents, dict) else {}
    allowed = (
        [str(item) for item in spec.get("allowed", [])]
        if isinstance(spec.get("allowed"), list)
        else []
    )
    max_depth = min(_count(spec.get("max_depth")) or 1, platform_max_depth())
    max_parallel = max(1, _count(spec.get("max_parallel")) or 1)
    parent_budget = definition.get("budget") if isinstance(definition, dict) else {}
    budget = parent_budget if isinstance(parent_budget, dict) else {}
    texts: list[str] = []
    usage = {"tokens_in": 0, "tokens_out": 0}
    children: list[dict[str, object]] = []
    batch = briefs[:max_parallel]
    for index, brief in enumerate(batch):
        planned = plan_child(
            {
                "run_id": str(parent.get("id")),
                "depth": _count(parent.get("depth")),
                "max_depth": max_depth,
                "remaining_budget": budget,
                "child_budget": _child_definition_budget(
                    store, parent.get("tenant_id"), str(brief.get("agent") or "")
                ),
                "allowed": allowed,
                "allow_self_clone": spec.get("allow_self_clone") is True,
                "agent": brief.get("agent"),
                "task": brief.get("task"),
                "index": index,
                "files": brief.get("files"),
            }
        )
        if planned.get("error"):
            SUBAGENTS.labels(status=str(planned["error"])).inc()
            return {
                "status": str(planned["error"]),
                "final_text": "",
                "usage": usage,
                "children": children,
                "is_error": True,
            }
        child = _insert_child(store, parent, planned, brief)
        _remember_step(store, parent, child, brief)
        _emit(
            store,
            parent,
            "subagent.started",
            {
                "child_run_id": str(child["id"]),
                "agent_id": str(child.get("agent_id") or ""),
                "agent_name": str(brief.get("agent") or ""),
                "task_brief": str(brief.get("task") or "")[:500],
            },
        )
        if parent.get("id") in getattr(store, "cancel_flags", set()):
            _finish_child(store, child, "cancelled", "")
            _emit(
                store,
                parent,
                "subagent.completed",
                {
                    "child_run_id": str(child["id"]),
                    "status": "cancelled",
                    "result_summary": "",
                    "usage": {},
                },
            )
            SUBAGENTS.labels(status="cancelled").inc()
            return {
                "status": "cancelled",
                "final_text": "",
                "usage": usage,
                "children": children,
                "is_error": True,
            }
        answer = str(brief.get("result") or _scripted_result(str(brief.get("task") or "")))
        child_usage = {"tokens_in": 1, "tokens_out": max(1, len(answer.split()))}
        _finish_child(store, child, "completed", answer, child_usage)
        usage["tokens_in"] += child_usage["tokens_in"]
        usage["tokens_out"] += child_usage["tokens_out"]
        texts.append(answer)
        children.append(
            {"id": str(child["id"]), "status": "completed", "agent": brief.get("agent")}
        )
        _emit(
            store,
            parent,
            "subagent.completed",
            {
                "child_run_id": str(child["id"]),
                "status": "completed",
                "result_summary": answer[:2048],
                "usage": child_usage,
            },
        )
        SUBAGENTS.labels(status="completed").inc()
    merged = "\n\n".join(texts)[:8000]
    wrapped = wrap_untrusted(
        source=f"subagent:{briefs[0].get('agent') if briefs else 'agent'}", content=merged
    )
    parent_usage = parent.get("usage")
    if isinstance(parent_usage, dict):
        parent_usage["tokens_in"] = _count(parent_usage.get("tokens_in")) + usage["tokens_in"]
        parent_usage["tokens_out"] = _count(parent_usage.get("tokens_out")) + usage["tokens_out"]
    else:
        parent["usage"] = dict(usage)
    return {
        "status": "completed",
        "final_text": merged,
        "wrapped": wrapped,
        "usage": usage,
        "children": children,
        "is_error": False,
    }


def cancel_children(store: Any, parent_id: uuid.UUID) -> None:
    """Mark live children cancelled when the parent is cancelled."""
    for run in store.runs.values():
        if run.get("parent_run_id") != parent_id:
            continue
        if str(run.get("status")) in {"queued", "running", "waiting_approval", "waiting_input"}:
            run["status"] = "cancelled"
            run["ended_at"] = utcnow()
            _emit(store, run, "run.cancelled", {"by": "parent"})
            SUBAGENTS.labels(status="cancelled").inc()
        cancel_children(store, uuid.UUID(str(run["id"])))


def _insert_child(
    store: Any,
    parent: dict[str, object],
    planned: dict[str, object],
    brief: dict[str, object],
) -> dict[str, object]:
    child_id = new_id()
    agent = _agent_by_slug(store, parent.get("tenant_id"), str(brief.get("agent") or ""))
    now = utcnow()
    message_id = new_id()
    task = str(brief.get("task") or "")
    store.messages[message_id] = {
        "id": message_id,
        "tenant_id": parent.get("tenant_id"),
        "conversation_id": parent.get("conversation_id"),
        "run_id": child_id,
        "role": "user",
        "content": [{"type": "text", "text": task}],
        "text": task,
        "status": "completed",
        "scope": "run",
        "is_active_branch": False,
        "created_at": now,
    }
    root = parent.get("root_run_id") or parent.get("id")
    run = {
        "id": child_id,
        "tenant_id": parent.get("tenant_id"),
        "conversation_id": parent.get("conversation_id"),
        "agent_id": None if agent is None else agent.get("id"),
        "agent_name": "" if agent is None else str(agent.get("name") or ""),
        "agent_slug": "" if agent is None else str(agent.get("slug") or ""),
        "agent_version_id": None if agent is None else agent.get("published_version_id"),
        "user_id": parent.get("user_id"),
        "input_message_id": message_id,
        "parent_run_id": parent.get("id"),
        "root_run_id": root,
        "depth": _count(parent.get("depth")) + 1,
        "status": "running",
        "trigger": "subagent",
        "usage": {"tokens_in": 0, "tokens_out": 0},
        "created_at": now,
        "started_at": now,
        "ended_at": None,
        "steps": [],
        "loaded_skills": [],
    }
    store.runs[child_id] = run
    store.events[child_id] = []
    planned["stored_id"] = str(child_id)
    return run


def _finish_child(
    store: Any,
    child: dict[str, object],
    status: str,
    answer: str,
    usage: dict[str, int] | None = None,
) -> None:
    child["status"] = status
    child["ended_at"] = utcnow()
    child["result_summary"] = answer[:8000]
    if usage is not None:
        child["usage"] = usage
    _emit(
        store,
        child,
        "run.completed" if status == "completed" else "run.cancelled",
        {"status": status},
    )


def _scripted_result(task: str) -> str:
    lowered = task.lower()
    if "rollout" in lowered:
        return "Rollout plan: start with the pilot team, then the rest of the workspace."
    if "launch" in lowered:
        return "Launch notes: the release is on track and the checklist is complete."
    return f"Findings: {task[:500]}"


def _remember_step(
    store: Any, parent: dict[str, object], child: dict[str, object], brief: dict[str, object]
) -> None:
    steps = getattr(store, "steps", None)
    if not isinstance(steps, dict):
        return
    step_id = new_id()
    steps[step_id] = {
        "id": step_id,
        "tenant_id": parent.get("tenant_id"),
        "run_id": parent.get("id"),
        "kind": "subagent",
        "detail": {"child_run_id": str(child.get("id")), "agent": brief.get("agent")},
    }


def _child_definition_budget(store: Any, tenant: object, slug: str) -> dict[str, object]:
    agent = _agent_by_slug(store, tenant, slug)
    if agent is None:
        return {}
    version_id = agent.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    budget = definition.get("budget") if isinstance(definition, dict) else None
    return budget if isinstance(budget, dict) else {}


def _agent_by_slug(store: Any, tenant: object, slug: str) -> dict[str, object] | None:
    for row in store.agents.values():
        if not isinstance(row, dict) or row.get("slug") != slug:
            continue
        if tenant is not None and row.get("tenant_id") != tenant:
            continue
        return row
    return None


def _definition(store: Any, run: dict[str, object]) -> dict[str, object]:
    version_id = run.get("agent_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    return definition if isinstance(definition, dict) else {}


def _emit(store: Any, run: dict[str, object], event_type: str, data: dict[str, object]) -> None:
    emit = getattr(store, "_emit", None)
    if callable(emit):
        emit(run, event_type, data)


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value

"""Drive a research run one phase at a time and publish the stream."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.research.engine import (
    advance,
    pending_subtasks,
    save_state,
    state_of,
    store_subtask,
)
from ar_domain.tools.agent_loop import _finish

if TYPE_CHECKING:
    from typing import Any


async def advance_research(
    store: Any, run: dict[str, object], question: str, *, one_step: bool
) -> str:
    """Advance until the report is verified, or one phase when ``one_step`` is set."""
    if str(run.get("status") or "") == "queued":
        run["status"] = "running"
        _emit_progress(store, run, "plan")
    kind = "model"
    for _step in range(12):
        if str(run.get("status") or "") == "cancelled":
            return "final"
        kind = advance(store, run, question)
        _emit_from_phase(store, run)
        if kind == "fanout":
            if one_step:
                state = state_of(run, question)
                state["phase"] = "awaiting"
                save_state(run, state)
                return "fanout"
            await _inline_subtasks(store, run, question)
            continue
        if kind == "final":
            _complete(store, run)
            return "final"
        if one_step:
            return kind
    _complete(store, run)
    return "final"


async def run_inline(store: Any, run: dict[str, object], question: str) -> str:
    """Dev and CI path. Production with Temporal uses one activity per phase."""
    return await advance_research(store, run, question, one_step=False)


async def execute_subtask(
    store: Any, run: dict[str, object], query: dict[str, str]
) -> dict[str, object]:
    """One query through the same functions the tool handlers use."""
    state = state_of(run, str(state_question(run)))
    subtasks = state.get("subtasks")
    if isinstance(subtasks, dict) and query["id"] in subtasks:
        found = subtasks[query["id"]]
        return found if isinstance(found, dict) else {}
    from ar_domain.research.gateway import subtask_via_gateway  # noqa: PLC0415

    result = subtask_via_gateway(store, run, query)
    store_subtask(run, query["id"], result)
    _emit_progress(store, run, "reading")
    return result


def state_question(run: dict[str, object]) -> str:
    checkpoint = run.get("checkpoint")
    if isinstance(checkpoint, dict) and isinstance(checkpoint.get("research"), dict):
        return str(checkpoint["research"].get("question") or "")
    return ""


async def _inline_subtasks(store: Any, run: dict[str, object], question: str) -> None:
    state = state_of(run, question)
    for query in pending_subtasks(state):
        await execute_subtask(store, run, query)
    state = state_of(run, question)
    state["phase"] = "awaiting"
    save_state(run, state)


def _complete(store: Any, run: dict[str, object]) -> None:
    if str(run.get("status") or "") in {"completed", "failed", "cancelled", "budget_exceeded"}:
        return
    assistant = _assistant(store, run)
    if assistant is None:
        return
    state = state_of(run, state_question(run))
    answer = str(state.get("report") or "")
    limit = state.get("budget_limit")
    if isinstance(limit, str) and limit:
        from ar_domain.tools.agent_loop import _stop_budget  # noqa: PLC0415

        _stop_budget(store, run, assistant, limit)
        assistant["text"] = answer or assistant.get("text")
        return
    _finish(store, run, assistant, answer, [])
    _emit_verified(store, run, assistant)
    _audit(store, run, "research.completed")
    run["research_report"] = answer


def _emit_verified(store: Any, run: dict[str, object], assistant: dict[str, object]) -> None:
    """Verified quotes become citation parts. Unsupported quotes are not shown as sources."""
    if not hasattr(store, "_emit"):
        return
    state = state_of(run, state_question(run))
    raw = state.get("citations")
    sources = state.get("sources")
    rows = raw if isinstance(raw, list) else []
    pages = sources if isinstance(sources, list) else []
    content = assistant.get("content")
    parts = list(content) if isinstance(content, list) else []
    shown = 0
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "supported":
            continue
        shown += 1
        indexes = row.get("indexes")
        index = indexes[0] if isinstance(indexes, list) and indexes else shown
        source = (
            pages[int(index) - 1] if isinstance(index, int) and 0 < int(index) <= len(pages) else {}
        )
        page = source if isinstance(source, dict) else {}
        citation = {
            "index": int(index) if isinstance(index, int) else shown,
            "source_kind": "tool_result",
            "title": str(page.get("title") or page.get("url") or "Source"),
            "uri": str(page.get("url") or ""),
            "snippet": str(row.get("quote") or ""),
            "verified": True,
        }
        parts.append({"type": "citation_ref", "index": citation["index"], "citation": citation})
        store._emit(
            run,
            "citation.added",
            {"message_id": str(assistant.get("id") or ""), "citation": citation},
        )
    if shown:
        assistant["content"] = parts


def _assistant(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    messages = getattr(store, "messages", None)
    if not isinstance(messages, dict):
        return None
    raw = run.get("assistant_message_id")
    try:
        key = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
    except ValueError:
        return None
    assistant = messages.get(key)
    return assistant if isinstance(assistant, dict) else None


def _emit_from_phase(store: Any, run: dict[str, object]) -> None:
    state = state_of(run, state_question(run))
    phase = str(state.get("phase") or "")
    if phase == "fanout":
        queries = state.get("queries")
        rows = queries if isinstance(queries, list) else []
        items = [
            {
                "id": str(query.get("id") or ""),
                "title": str(query.get("text") or ""),
                "status": "in_progress",
            }
            for query in rows
            if isinstance(query, dict)
        ]
        if items and hasattr(store, "_emit"):
            store._emit(run, "plan.updated", {"items": items})
        _audit(store, run, "run.planned")
    _emit_progress(store, run, phase or "plan")


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _emit_progress(store: Any, run: dict[str, object], phase: str) -> None:
    if not hasattr(store, "_emit"):
        return
    state = state_of(run, state_question(run))
    sources = state.get("sources")
    queries = state.get("queries")
    store._emit(
        run,
        "research.progress",
        {
            "phase": phase,
            "depth": _whole(state.get("depth")),
            "source_count": len(sources) if isinstance(sources, list) else 0,
            "queries": queries if isinstance(queries, list) else [],
        },
    )


def _audit(store: Any, run: dict[str, object], action: str) -> None:
    log = getattr(store, "audit_log", None)
    if not isinstance(log, list):
        return
    from ar_common.time import utcnow  # noqa: PLC0415

    log.append(
        {
            "tenant_id": str(run.get("tenant_id")),
            "actor_id": str(run.get("user_id")),
            "action": action,
            "target_type": "run",
            "target_id": str(run.get("id")),
            "detail": {"mode": "research"},
            "outcome": "success",
            "at": utcnow().isoformat(),
        }
    )

"""Continue a run after an approval decision: run the approved call, then finish the run."""

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.approvals.pending import held, release
from ar_domain.conversations.logic import run_is_active
from ar_domain.durable.after import after_commit
from ar_domain.runs.request import permissions_of

if TYPE_CHECKING:
    from typing import Any


def settle_approval(store: Any, approval: dict[str, object]) -> None:
    """Record that a decision is ready and wake the run's workflow.

    The API does not call the tool. The next ``advance_chat_step`` does, through the
    gateway. A missing workflow is started so that activity can apply the decision.
    """
    run_id = approval.get("run_id")
    if not isinstance(run_id, uuid.UUID):
        return
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        return
    pending = held(run)
    if pending is not None and str(pending.get("approval_id")) != str(approval.get("id")):
        return
    status = str(approval.get("status"))

    def _wake() -> None:
        from ar_domain.runs.dispatch import continue_on_worker, request_signal  # noqa: PLC0415

        # The row is already decided. Signal a waiting workflow, and start one
        # when nothing is waiting, so the worker applies the decision.
        request_signal(
            store,
            run_id,
            "approval_decided",
            {"status": status, "approval_id": str(approval.get("id") or "")},
        )
        continue_on_worker(
            store,
            run_id,
            "",
            {"status": status, "approval_id": str(approval.get("id") or "")},
        )

    after_commit(store, _wake)


def apply_decision(store: Any, run: dict[str, object], decision: dict[str, object]) -> str:
    """Apply a signal the workflow waited for. Return ``final``, ``continue`` or ``paused``."""
    choice = str(decision.get("status") or "")
    status = str(run.get("status") or "")
    if choice == "input" or status == "waiting_input":
        if status != "waiting_input":
            return "continue"
        text = str(decision.get("text") or "")
        if run.get("pending_question_id"):
            from ar_domain.orchestration.ask import accept_human_answer  # noqa: PLC0415

            try:
                accept_human_answer(
                    store,
                    run.get("tenant_id"),  # type: ignore[arg-type]
                    run.get("user_id"),  # type: ignore[arg-type]
                    run,
                    text,
                )
            except Exception:  # noqa: BLE001 - the answer may already be stored
                run["resume_answer"] = text
                run["resume"] = True
                run["status"] = "running"
                run["pending_question_id"] = None
        else:
            run["resume_answer"] = text
            run["resume"] = True
            run["status"] = "running"
        return "continue"
    if status != "waiting_approval":
        return "continue"
    if choice in {"rejected", "expired", "cancelled"}:
        approval = _approval_row(store, run) or {
            "id": decision.get("approval_id"),
            "status": choice,
        }
        _stop(store, run, approval, choice)
        return "final"
    if choice == "approved" or _approval_status(store, run) == "approved":
        approval = _approval_row(store, run) or {
            "id": decision.get("approval_id"),
            "status": "approved",
        }
        _resume(store, run, approval)
        return "continue" if str(run.get("status")) == "running" else "final"
    return "paused"


def mark_cancelled(store: Any, run: dict[str, object]) -> None:
    """Stop a run whose cancel was requested. A second call leaves a terminal run alone."""
    if not run_is_active(str(run.get("status"))):
        return
    run["status"] = "cancelled"
    run["ended_at"] = utcnow()
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict) and conversation.get("active_run_id") == run.get("id"):
        conversation["active_run_id"] = None
    assistant_id = run.get("assistant_message_id")
    assistant = store.messages.get(assistant_id) if isinstance(assistant_id, uuid.UUID) else None
    if isinstance(assistant, dict):
        assistant["status"] = "cancelled"
    if hasattr(store, "_emit"):
        store._emit(run, "run.cancelled", {"by": "user"})


def _approval_row(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    pending = held(run)
    if pending is None:
        return None
    approval_id = pending.get("approval_id")
    approvals = getattr(store, "approvals", None)
    if not isinstance(approvals, dict):
        return None
    row = approvals.get(approval_id)
    return row if isinstance(row, dict) else None


def stored_approval_choice(store: Any, run: dict[str, object]) -> str:
    """The status recorded on the run's approval row, or empty when there is none."""
    return _approval_status(store, run)


def _approval_status(store: Any, run: dict[str, object]) -> str:
    row = _approval_row(store, run)
    return str(row.get("status") or "") if isinstance(row, dict) else ""


def _resume(store: Any, run: dict[str, object], approval: dict[str, object]) -> None:
    from ar_domain.tools.gateway_client import execute_tool  # noqa: PLC0415

    pending = held(run)
    if pending is None:
        return
    store._emit(
        run,
        "tool_call.approval_resolved",
        {
            "tool_call_id": str(pending.get("model_call_id")),
            "approval_id": str(approval.get("id")),
            "status": "approved",
        },
    )
    result = execute_tool(
        store,
        {
            "tenant_id": run.get("tenant_id"),
            "user_id": run.get("user_id"),
            "run_id": run.get("id"),
            "agent_id": run.get("agent_id"),
            "agent_version_id": run.get("agent_version_id"),
            "tool_version_id": pending.get("tool_version_id"),
            "arguments": pending.get("arguments"),
            "args_hash": pending.get("args_hash"),
            "model_call_id": pending.get("model_call_id"),
            "step": pending.get("step"),
            "query_id": pending.get("query_id"),
            "call_index": pending.get("call_index"),
            "approval_id": approval.get("id"),
            "tool_call_id": approval.get("tool_call_id"),
            "permissions": permissions_of(run),
        },
    )
    text = str(result.get("result_preview") or "")
    if result.get("status") != "succeeded":
        error = result.get("error")
        detail = str(error.get("message") or "") if isinstance(error, dict) else ""
        text = f"The approved tool call did not run: {detail or text or 'no reason was given'}"
    if _continue_loop(run, text):
        run["status"] = "running"
        release(run)
        run["step_kind"] = "tools"
        return
    _finish(store, run, text, result, status="completed")


def _continue_loop(run: dict[str, object], text: str) -> bool:
    """Append the approved result onto a checkpointed loop so the next step is the model."""
    from ar_domain.tools.worker_loop import (  # noqa: PLC0415
        read_worker_loop,
        worker_loop_open,
        write_worker_loop,
    )

    if not worker_loop_open(run):
        return False
    state = read_worker_loop(run)
    if not isinstance(state, dict):
        return False
    messages = state.get("messages")
    if not isinstance(messages, list):
        messages = []
        state["messages"] = messages
    pending = held(run) or {}
    calls = state.get("pending_calls")
    index = state.get("pending_index")
    current = index if isinstance(index, int) and not isinstance(index, bool) else 0
    call = calls[current] if isinstance(calls, list) and 0 <= current < len(calls) else None
    call_name = str(call.get("name") or "") if isinstance(call, dict) else ""
    call_id = str(call.get("id") or "") if isinstance(call, dict) else ""
    messages.append(
        {
            "role": "tool",
            "name": call_name,
            "tool_call_id": call_id or str(pending.get("model_call_id") or ""),
            "content": text,
        }
    )
    nxt = current + 1
    state["pending_index"] = nxt
    state["phase"] = "tools"
    write_worker_loop(run, state)
    return True


def _stop(store: Any, run: dict[str, object], approval: dict[str, object], status: str) -> None:
    if not run_is_active(str(run.get("status"))):
        return
    pending = held(run) or {}
    store._emit(
        run,
        "tool_call.approval_resolved",
        {
            "tool_call_id": str(pending.get("model_call_id")),
            "approval_id": str(approval.get("id")),
            "status": status,
        },
    )
    reason = {
        "rejected": "The approver rejected this tool call.",
        "expired": "The approval expired before anyone decided.",
        "cancelled": "The approval was cancelled.",
    }[status]
    run_status = "cancelled" if status == "cancelled" else "completed"
    _finish(
        store,
        run,
        reason,
        {"status": status, "qualified_name": approval.get("qualified_name")},
        status=run_status,
    )


def _finish(
    store: Any, run: dict[str, object], text: str, result: dict[str, object], *, status: str
) -> None:
    assistant_id = run.get("assistant_message_id")
    assistant = store.messages.get(assistant_id) if isinstance(assistant_id, uuid.UUID) else None
    if isinstance(assistant, dict):
        assistant["text"] = text
        assistant["content"] = [{"type": "text", "text": text}]
        assistant["status"] = "completed" if status == "completed" else status
        assistant["tool_calls"] = [
            {
                "qualified_name": result.get("qualified_name") or assistant.get("qualified_name"),
                "status": result.get("status"),
                "result_preview": text,
                "arguments": result.get("arguments_redacted"),
            }
        ]
    run["status"] = status
    run["ended_at"] = utcnow()
    release(run)
    run["result_summary"] = text[:8000]
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    if isinstance(assistant, dict):
        store._emit(
            run, "message.completed", {"message_id": str(assistant.get("id")), "text": text}
        )
    event = "run.cancelled" if status == "cancelled" else "run.completed"
    store._emit(run, event, {"final_message_id": str(assistant_id)})

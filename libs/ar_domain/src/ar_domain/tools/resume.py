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


def settle_held_call(store: Any, approval: dict[str, object]) -> None:
    """Move the tool call the approval is about off ``awaiting_approval``.

    The decision is recorded on that row. The later execution of an approved call
    writes its outcome onto the same row, so a second row is not the only place
    the result exists.
    """
    decision = str(approval.get("status") or "")
    status = {
        "approved": "approved",
        "rejected": "rejected",
        "expired": "expired",
        "cancelled": "cancelled",
    }.get(decision, "failed")
    calls = getattr(store, "tool_calls", None)
    if not isinstance(calls, dict):
        return
    call_id = approval.get("tool_call_id")
    call = calls.get(call_id)
    if not isinstance(call, dict):
        call = next(
            (
                row
                for row in calls.values()
                if isinstance(row, dict) and row.get("approval_id") == approval.get("id")
            ),
            None,
        )
    if isinstance(call, dict) and str(call.get("status") or "") == "awaiting_approval":
        call["status"] = status
        if decision != "approved":
            call["is_error"] = True
            call["error"] = {"code": status, "message": f"The approval was {decision}."}


def settle_approval(store: Any, approval: dict[str, object]) -> None:
    """Record that a decision is ready and wake the run's workflow.

    The API does not call the tool. The next ``advance_chat_step`` does, through the
    gateway. A missing workflow is started so that activity can apply the decision.
    """
    settle_held_call(store, approval)
    from ar_domain.routines.engine import is_delivery_tool  # noqa: PLC0415

    if is_delivery_tool(approval.get("qualified_name")):
        # A routine's delivery is asked about after its run has ended: no run waits for it.
        from ar_domain.routines.dispatch import delivery_decided  # noqa: PLC0415

        delivery_decided(store, approval)
        return
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
    if choice == "input" or (status == "waiting_input" and choice not in {"approved", "rejected"}):
        if choice != "input" and status != "waiting_input":
            return "continue"
        text = str(decision.get("text") or "")
        from ar_domain.orchestration.ask import accept_human_answer, question_for_run  # noqa: PLC0415

        if question_for_run(store, run) is not None:
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
        _fold_input(run, text)
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


_WAITING = "Waiting for approval before this tool runs."
_INTERRUPTED = (
    "The tool call did not finish in time. It was stopped, and whether it "
    "changed anything is not known. Check before asking for it again."
)


def fail_interrupted_tool(store: Any, run: dict[str, object]) -> None:
    """A step cut off while a tool was running. The reply says so, and the call is failed."""
    from ar_domain.runs.failure import fail_run  # noqa: PLC0415

    if not run_is_active(str(run.get("status"))):
        return
    assistant_id = run.get("assistant_message_id")
    messages = getattr(store, "messages", {})
    assistant = messages.get(assistant_id) if isinstance(messages, dict) else None
    if isinstance(assistant, dict):
        said = str(assistant.get("text") or "")
        if not said or said == _WAITING:
            assistant["text"] = _INTERRUPTED
            assistant["content"] = [{"type": "text", "text": _INTERRUPTED}]
        calls = assistant.get("tool_calls")
        if isinstance(calls, list):
            for call in calls:
                if isinstance(call, dict) and str(call.get("status") or "") in {
                    "awaiting_approval",
                    "running",
                }:
                    call["status"] = "failed"
                    call["result_preview"] = _INTERRUPTED
                    call["error"] = {"code": "upstream_timeout", "message": _INTERRUPTED}
    calls_book = getattr(store, "tool_calls", {})
    if isinstance(calls_book, dict):
        for row in calls_book.values():
            if (
                isinstance(row, dict)
                and row.get("run_id") == run.get("id")
                and str(row.get("status") or "") in {"awaiting_approval", "running"}
            ):
                row["status"] = "failed"
                row["is_error"] = True
                row["error"] = {"code": "upstream_timeout", "message": _INTERRUPTED}
                row["result_preview"] = _INTERRUPTED
    fail_run(
        store,
        run,
        code="upstream_timeout",
        message=_INTERRUPTED,
        reason="tool_timeout",
        assistant=assistant if isinstance(assistant, dict) else None,
    )


_CUT_OFF = "This answer was stopped because it took too long. Please ask again."


def fail_cut_off(store: Any, run: dict[str, object], reason: str) -> None:
    """A step the platform stopped (it ran out of time, or its worker shut down).

    Nobody asked for it, so it is a failed run that says so, not a cancel by the person.
    """
    from ar_domain.runs.failure import fail_run  # noqa: PLC0415

    if not run_is_active(str(run.get("status"))):
        return
    messages = getattr(store, "messages", {})
    assistant = (
        messages.get(run.get("assistant_message_id")) if isinstance(messages, dict) else None
    )
    fail_run(
        store,
        run,
        code="upstream_timeout",
        message=_CUT_OFF,
        reason=reason,
        assistant=assistant if isinstance(assistant, dict) else None,
    )


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
    result_status = str(result.get("status") or "failed")
    if result_status != "succeeded":
        error = result.get("error")
        detail = str(error.get("message") or "") if isinstance(error, dict) else ""
        text = f"The approved tool call did not run: {detail or text or 'no reason was given'}"
    if _continue_loop(run, text, status=result_status, error=result.get("error")):
        run["status"] = "running"
        release(run)
        run["step_kind"] = "tools"
        return
    _finish(store, run, text, result, status="completed")


def _fold_input(run: dict[str, object], text: str) -> None:
    """Put the person's answer on the paused ask and let the next step be the model."""
    from ar_domain.tools.worker_loop import read_worker_loop, write_worker_loop  # noqa: PLC0415

    state = read_worker_loop(run)
    if not isinstance(state, dict):
        return
    messages = state.get("messages")
    if not isinstance(messages, list):
        messages = []
        state["messages"] = messages
    calls = state.get("pending_calls")
    index = state.get("pending_index")
    current = index if isinstance(index, int) and not isinstance(index, bool) else 0
    call = calls[current] if isinstance(calls, list) and 0 <= current < len(calls) else None
    call_id = str(call.get("id") or "ask") if isinstance(call, dict) else "ask"
    already = any(
        isinstance(item, dict)
        and item.get("role") == "tool"
        and str(item.get("tool_call_id") or "") == call_id
        and "The person answered:" in str(item.get("content") or "")
        for item in messages
    )
    if not already:
        from ar_common.wrapping import wrap_tool_result  # noqa: PLC0415

        messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": wrap_tool_result(
                    tool="agents_ask",
                    call_id=call_id,
                    content=f"The person answered: {text}",
                ),
            }
        )
    state["pending_index"] = current + 1
    state["phase"] = "model"
    state["pending_calls"] = []
    write_worker_loop(run, state)


def _continue_loop(
    run: dict[str, object],
    text: str,
    *,
    status: str = "succeeded",
    error: object = None,
) -> bool:
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
    pending_len = len(calls) if isinstance(calls, list) else 0
    state["phase"] = "model" if nxt >= pending_len else "tools"
    previews = state.get("previews")
    if not isinstance(previews, list):
        previews = []
        state["previews"] = previews
    preview: dict[str, object] = {
        "qualified_name": call_name.replace("__", "."),
        "status": status,
        "result_preview": text,
    }
    if error is not None:
        preview["error"] = error
    previews.append(preview)
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
    # A called agent's run ends inside its caller's turn, which still has the conversation.
    if isinstance(conversation, dict) and run.get("parent_run_id") is None:
        conversation["active_run_id"] = None
    if isinstance(assistant, dict):
        store._emit(
            run, "message.completed", {"message_id": str(assistant.get("id")), "text": text}
        )
    event = "run.cancelled" if status == "cancelled" else "run.completed"
    store._emit(run, event, {"final_message_id": str(assistant_id)})

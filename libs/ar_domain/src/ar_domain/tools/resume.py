"""Resume a run after an approval decision. The dev API does this in process."""

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.conversations.logic import run_is_active

if TYPE_CHECKING:
    from typing import Any


def settle_approval(store: Any, approval: dict[str, object]) -> None:
    """Continue, reject or cancel the run that is waiting on this approval."""
    run_id = approval.get("run_id")
    if not isinstance(run_id, uuid.UUID):
        return
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        return
    pending = run.get("pending_approval")
    if isinstance(pending, dict) and str(pending.get("approval_id")) != str(approval.get("id")):
        return
    status = str(approval.get("status"))
    if status == "approved":
        _resume(store, run, approval)
        return
    if status in {"rejected", "expired", "cancelled"}:
        _stop(store, run, approval, status)


def _resume(store: Any, run: dict[str, object], approval: dict[str, object]) -> None:
    from ar_domain.tools.pipeline import ToolPipeline  # noqa: PLC0415

    pending = run.get("pending_approval")
    if not isinstance(pending, dict):
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
    result = ToolPipeline(store).execute(
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
            "approval_id": approval.get("id"),
            "tool_call_id": approval.get("tool_call_id"),
        }
    )
    text = str(result.get("result_preview") or "")
    _finish(store, run, text, result, status="completed")


def _stop(store: Any, run: dict[str, object], approval: dict[str, object], status: str) -> None:
    if not run_is_active(str(run.get("status"))):
        return
    raw_pending = run.get("pending_approval")
    pending = raw_pending if isinstance(raw_pending, dict) else {}
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
    run["pending_approval"] = None
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

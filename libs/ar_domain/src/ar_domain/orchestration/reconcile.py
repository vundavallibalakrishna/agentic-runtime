"""Mark runs that were in flight when the process stopped."""

from __future__ import annotations

from typing import Any  # noqa: TC003

from ar_common.time import utcnow

_INTERRUPTED = (
    "The API restarted while this run was working. It was marked failed and was not resumed."
)


def reconcile_interrupted(store: Any) -> list[str]:
    """Fail `running` rows loaded from a previous process. Paused runs stay paused."""
    changed: list[str] = []
    runs = getattr(store, "runs", {})
    if not isinstance(runs, dict):
        return changed
    for run in list(runs.values()):
        if not isinstance(run, dict) or str(run.get("status")) != "running":
            continue
        _fail(store, run)
        changed.append(str(run.get("id")))
    return changed


def _fail(store: Any, run: dict[str, object]) -> None:
    run["status"] = "failed"
    run["ended_at"] = utcnow()
    run["error"] = {"code": "interrupted", "message": _INTERRUPTED}
    run["result_summary"] = _INTERRUPTED
    conversations = getattr(store, "conversations", {})
    conversation = (
        conversations.get(run.get("conversation_id")) if isinstance(conversations, dict) else None
    )
    if isinstance(conversation, dict) and conversation.get("active_run_id") == run.get("id"):
        conversation["active_run_id"] = None
    messages = getattr(store, "messages", {})
    assistant = (
        messages.get(run.get("assistant_message_id")) if isinstance(messages, dict) else None
    )
    if isinstance(assistant, dict) and not str(assistant.get("text") or ""):
        assistant["text"] = _INTERRUPTED
        assistant["status"] = "completed"
        assistant["content"] = [{"type": "text", "text": _INTERRUPTED}]
    emit = getattr(store, "_emit", None)
    if callable(emit):
        emit(run, "run.failed", {"error": run["error"]})
    audit = getattr(store, "audit_log", None)
    if isinstance(audit, list):
        audit.append(
            {
                "tenant_id": str(run.get("tenant_id")),
                "actor_id": "system",
                "action": "run.interrupted",
                "target_type": "run",
                "target_id": str(run.get("id")),
                "detail": {"code": "interrupted"},
                "outcome": "failure",
                "at": utcnow().isoformat(),
            }
        )

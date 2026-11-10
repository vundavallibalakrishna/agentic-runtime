"""One way to end a run that failed. Spec: docs/03-specs/06-conversations-runs.md §5.

A failed run used to mark the reply it was making as completed, with the reason in its
text. On the screen that read as an answer from the agent, with nothing to say it had
failed and nothing to do about it. Every failure now ends here, so the reply is marked
failed, the reason travels with it, and a later turn is not given it as an answer.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def fail_run(
    store: Any,
    run: dict[str, object],
    *,
    code: str,
    message: str,
    reason: str | None = None,
    assistant: dict[str, object] | None = None,
) -> None:
    """Mark the run failed with ``code`` and ``message``, and its reply failed too.

    Whatever the reply had already said is kept. A reply with no text gets the message,
    so a reader of the message alone still learns what happened. The conversation is
    free for a next turn.
    """
    run["status"] = "failed"
    run["ended_at"] = utcnow()
    error: dict[str, object] = {"code": code, "message": message}
    if reason:
        error["reason"] = reason
    run["error"] = error
    run["result_summary"] = message
    conversations = getattr(store, "conversations", {})
    conversation = conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict) and conversation.get("active_run_id") in {
        run.get("id"),
        None,
    }:
        conversation["active_run_id"] = None
    reply = assistant if assistant is not None else _reply(store, run)
    if isinstance(reply, dict):
        said = str(reply.get("text") or "")
        reply["status"] = "failed"
        if not said:
            reply["text"] = message
            reply["content"] = [{"type": "text", "text": message}]
    emit = getattr(store, "_emit", None)
    if callable(emit):
        emit(run, "run.failed", {"error": run["error"]})


def _reply(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    messages = getattr(store, "messages", None)
    key = run.get("assistant_message_id")
    if not isinstance(messages, dict) or not isinstance(key, uuid.UUID):
        return None
    found = messages.get(key)
    return found if isinstance(found, dict) else None


def reply_error(store: Any, message: dict[str, object]) -> dict[str, object] | None:
    """The run's error for a reply that failed, for whoever shows the message."""
    if message.get("role") != "assistant" or message.get("status") != "failed":
        return None
    runs = getattr(store, "runs", None)
    run = runs.get(message.get("run_id")) if isinstance(runs, dict) else None
    error = run.get("error") if isinstance(run, dict) else None
    return dict(error) if isinstance(error, dict) else None

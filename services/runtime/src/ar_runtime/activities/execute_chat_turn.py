"""Run one chat turn. The activity is safe to retry once the run has finished."""

import asyncio
import contextlib
import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_runtime.activities.expire_approval import current_store


@activity.defn(name="execute_chat_turn")
async def execute_chat_turn(payload: dict[str, Any]) -> dict[str, str]:
    """Reload the queued run, generate the answer, and flush it."""
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None or not hasattr(store, "generate"):
        return {"status": "missing_store", "run_id": str(run_id)}
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    await reload_run(store, run_id)
    run = getattr(store, "runs", {}).get(run_id)
    if isinstance(run, dict) and run.get("status") in {"completed", "failed", "cancelled"}:
        return {"status": str(run["status"]), "run_id": str(run_id)}
    from ar_common.errors import QuotaExceededError  # noqa: PLC0415
    from ar_runtime.activities.start_run import assert_start  # noqa: PLC0415

    try:
        assert_start(store, run_id)
    except QuotaExceededError as exc:
        from ar_domain.chat.service import ChatService  # noqa: PLC0415

        runs = getattr(store, "runs", None)
        run = runs.get(run_id) if isinstance(runs, dict) else None
        if isinstance(store, ChatService) and isinstance(run, dict):
            store._fail_quota(
                run,
                store.conversations[run["conversation_id"]],
                store.messages[run["assistant_message_id"]],
                exc,
            )
        await flush_store(store)
        return {"status": "quota_exceeded", "run_id": str(run_id)}
    source = (
        getattr(store, "messages", {}).get(run.get("input_message_id"), {})
        if isinstance(run, dict)
        else {}
    )
    text = str(source.get("text") or payload.get("text") or "")
    parts = source.get("content")
    raw_names = (
        [
            str(part.get("name") or "")
            for part in parts
            if isinstance(part, dict) and part.get("type") == "file"
        ]
        if isinstance(parts, list)
        else payload.get("names")
    )
    names = [str(item) for item in raw_names] if isinstance(raw_names, list) else []
    heartbeat = asyncio.create_task(_heartbeat()) if activity.in_activity() else None
    try:
        await store.generate(run_id, text, names)
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
    await flush_store(store)
    runs = getattr(store, "runs", None)
    run = runs.get(run_id, {}) if isinstance(runs, dict) else {}
    status = str(run.get("status") or "completed") if isinstance(run, dict) else "completed"
    return {"status": status, "run_id": str(run_id)}


async def _heartbeat() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(2)


@activity.defn(name="finish_chat_turn")
async def finish_chat_turn(payload: dict[str, Any]) -> dict[str, str]:
    """Persist cancellation or exhausted retries so clients never wait indefinitely."""
    from ar_common.time import utcnow  # noqa: PLC0415
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    store = current_store()
    if not isinstance(store, ChatService):
        raise TypeError("runtime store is not bound")
    run_id = uuid.UUID(str(payload["run_id"]))
    await flush_store(store)
    await reload_run(store, run_id)
    run = store.runs[run_id]
    if run.get("status") in {"completed", "failed", "cancelled"}:
        return {"run_id": str(run_id), "status": str(run["status"])}
    status = "cancelled" if payload.get("status") == "cancelled" else "failed"
    run["status"] = status
    run["ended_at"] = utcnow()
    conversation = store.conversations[uuid.UUID(str(run["conversation_id"]))]
    if conversation.get("active_run_id") == run_id:
        conversation["active_run_id"] = None
    assistant = store.messages.get(uuid.UUID(str(run["assistant_message_id"])))
    if isinstance(assistant, dict):
        assistant["status"] = "cancelled" if status == "cancelled" else "completed"
    event_data: dict[str, object] = {"by": "user"}
    if status == "failed":
        run["error"] = {
            "code": "internal_error",
            "message": "The agent could not finish this reply. Please try again.",
        }
        event_data = {"error": run["error"]}
    store._emit(run, f"run.{status}", event_data)
    await flush_store(store)
    return {"run_id": str(run_id), "status": status}

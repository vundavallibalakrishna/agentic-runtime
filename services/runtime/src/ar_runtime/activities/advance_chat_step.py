"""One step of a chat turn: a model call or a single tool call."""

import asyncio
import contextlib
import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_runtime.activities.expire_approval import current_store


@activity.defn(name="advance_chat_step")
async def advance_chat_step(payload: dict[str, Any]) -> dict[str, str]:
    """Reload the run and advance it by one step. A finished run is not run again."""
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None or not hasattr(store, "advance_turn"):
        return {"status": "missing_store", "kind": "final", "run_id": str(run_id)}
    from ar_domain.conversations.logic import run_is_active  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(store)
    await reload_run(store, run_id)
    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict):
        return {"status": "missing", "kind": "final", "run_id": str(run_id)}
    status = str(run.get("status") or "")
    if not run_is_active(status):
        await flush_store(store)
        return {"status": status, "kind": "final", "run_id": str(run_id)}
    if status == "queued":
        from ar_common.errors import QuotaExceededError  # noqa: PLC0415
        from ar_domain.chat.service import ChatService  # noqa: PLC0415
        from ar_runtime.activities.start_run import assert_start  # noqa: PLC0415

        try:
            assert_start(store, run_id)
        except QuotaExceededError as exc:
            if isinstance(store, ChatService):
                store._fail_quota(
                    run,
                    store.conversations[run["conversation_id"]],
                    store.messages[run["assistant_message_id"]],
                    exc,
                )
            await flush_store(store)
            return {"status": "quota_exceeded", "kind": "final", "run_id": str(run_id)}
    source = getattr(store, "messages", {}).get(run.get("input_message_id"), {})
    text = str(source.get("text") or payload.get("text") or "") if isinstance(source, dict) else ""
    parts = source.get("content") if isinstance(source, dict) else None
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
        kind = await store.advance_turn(run_id, text, names)
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
    await flush_store(store)
    run = runs.get(run_id, {}) if isinstance(runs, dict) else {}
    status = str(run.get("status") or "completed") if isinstance(run, dict) else "completed"
    if not run_is_active(status):
        kind = "final"
    return {"status": status, "kind": str(kind), "run_id": str(run_id)}


async def _heartbeat() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(2)

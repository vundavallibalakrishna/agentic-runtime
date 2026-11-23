"""Run one chat turn. The activity is safe to retry once the run has finished."""

import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_domain.readmodel.activity import repository_activity
from ar_runtime.activities.expire_approval import current_store, process_store
from ar_runtime.activities.heartbeat import heartbeating


@activity.defn(name="execute_chat_turn")
@repository_activity(process_store)
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
        # An earlier attempt may have finished the turn and then failed to save it. The
        # finished run is then only in memory, so save before reporting it as done.
        await flush_store(store)
        return {"status": str(run["status"]), "run_id": str(run_id)}
    from ar_common.errors import QuotaExceededError  # noqa: PLC0415
    from ar_runtime.activities.start_run import assert_start  # noqa: PLC0415

    try:
        assert_start(store, run_id)
    except QuotaExceededError as exc:
        from ar_domain.chat.service import ChatBehaviour  # noqa: PLC0415

        runs = getattr(store, "runs", None)
        run = runs.get(run_id) if isinstance(runs, dict) else None
        if isinstance(store, ChatBehaviour) and isinstance(run, dict):
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
    async with heartbeating():
        await store.generate(run_id, text, names)
    await flush_store(store)
    runs = getattr(store, "runs", None)
    run = runs.get(run_id, {}) if isinstance(runs, dict) else {}
    status = str(run.get("status") or "completed") if isinstance(run, dict) else "completed"
    return {"status": status, "run_id": str(run_id)}


def stop_words(payload: dict[str, Any]) -> tuple[str, str]:
    """Why the workflow ended a run that did not end itself, and what to tell its reader."""
    if payload.get("reason") == "step_limit":
        allowed = payload.get("max_steps")
        count = f"all {allowed} steps" if isinstance(allowed, int) else "all the steps"
        return (
            "step_limit",
            f"The run used {count} its budget allows and was stopped before it finished. "
            "Raise the step or tool-call limit on the agent, or on the routine if it has a "
            "lower one, or ask for less in one run.",
        )
    reason = str(payload.get("reason") or "step_failed")
    return reason, "The agent could not finish this reply. Please try again."


@activity.defn(name="finish_chat_turn")
@repository_activity(process_store)
async def finish_chat_turn(payload: dict[str, Any]) -> dict[str, str]:
    """Persist cancellation or exhausted retries so clients never wait indefinitely."""
    from ar_common.time import utcnow  # noqa: PLC0415
    from ar_domain.chat.service import ChatBehaviour  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    store = current_store()
    if not isinstance(store, ChatBehaviour):
        raise TypeError("runtime store is not bound")
    run_id = uuid.UUID(str(payload["run_id"]))
    await flush_store(store)
    await reload_run(store, run_id)
    run = store.runs[run_id]
    if run.get("status") in {"completed", "failed", "cancelled"}:
        return {"run_id": str(run_id), "status": str(run["status"])}
    if payload.get("status") != "cancelled":
        from ar_common.logging import get_logger  # noqa: PLC0415
        from ar_domain.runs.failure import fail_run  # noqa: PLC0415

        reason, message = stop_words(payload)
        # No content: the run, why the workflow ended it, and how far it had got.
        get_logger(__name__).warning(
            "run_ended_by_workflow",
            run_id=str(run_id),
            reason=reason,
            steps=payload.get("steps"),
            max_steps=payload.get("max_steps"),
        )
        fail_run(store, run, code="internal_error", message=message, reason=reason)
    else:
        run["status"] = "cancelled"
        run["ended_at"] = utcnow()
        conversation = store.conversations[uuid.UUID(str(run["conversation_id"]))]
        if conversation.get("active_run_id") == run_id:
            conversation["active_run_id"] = None
        assistant = store.messages.get(uuid.UUID(str(run["assistant_message_id"])))
        if isinstance(assistant, dict):
            assistant["status"] = "cancelled"
        store._emit(run, "run.cancelled", {"by": "user"})
    await flush_store(store)
    return {"run_id": str(run_id), "status": str(run["status"])}

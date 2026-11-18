"""One step of a chat turn: a model call or a single tool call."""

import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_domain.readmodel.activity import repository_activity
from ar_runtime.activities.expire_approval import current_store, process_store
from ar_runtime.activities.heartbeat import heartbeating


@activity.defn(name="advance_chat_step")
@repository_activity(process_store)
async def advance_chat_step(payload: dict[str, Any]) -> dict[str, Any]:
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
    stopped = await _stop_or_apply(store, run, run_id, payload)
    if stopped is not None:
        await flush_store(store)
        return stopped
    status = str(run.get("status") or "")
    if not run_is_active(status):
        await flush_store(store)
        return {"status": status, "kind": "final", "run_id": str(run_id)}
    if status == "queued":
        from ar_common.errors import QuotaExceededError  # noqa: PLC0415
        from ar_domain.chat.service import ChatBehaviour  # noqa: PLC0415
        from ar_runtime.activities.start_run import assert_start  # noqa: PLC0415

        try:
            assert_start(store, run_id)
        except QuotaExceededError as exc:
            if isinstance(store, ChatBehaviour):
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
    async with heartbeating():
        kind = await store.advance_turn(run_id, text, names)
    await flush_store(store)
    run = runs.get(run_id, {}) if isinstance(runs, dict) else {}
    status = str(run.get("status") or "completed") if isinstance(run, dict) else "completed"
    if not run_is_active(status):
        kind = "final"
    return _step_body(run if isinstance(run, dict) else {}, status, str(kind), str(run_id), text)


async def _stop_or_apply(
    store: object, run: dict[str, Any], run_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any] | None:
    """Cancel or apply a waited decision. None means the step should run."""
    from ar_domain.conversations.logic import run_is_active  # noqa: PLC0415

    status = str(run.get("status") or "")
    if run.get("cancel_requested") is True and run_is_active(status):
        from ar_domain.tools.resume import mark_cancelled  # noqa: PLC0415

        mark_cancelled(store, run)
        return {"status": "cancelled", "kind": "final", "run_id": str(run_id)}
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        return None
    from ar_domain.tools.resume import apply_decision  # noqa: PLC0415

    applied = apply_decision(store, run, decision)
    if applied == "final" or not run_is_active(str(run.get("status") or "")):
        return {
            "status": str(run.get("status") or "completed"),
            "kind": "final",
            "run_id": str(run_id),
        }
    return None


def _step_body(
    run: dict[str, Any], status: str, kind: str, run_id: str, text: str
) -> dict[str, Any]:
    body: dict[str, Any] = {"status": status, "kind": kind, "run_id": run_id}
    if kind == "paused" and status == "waiting_approval":
        from ar_domain.approvals.pending import held  # noqa: PLC0415

        pending = held(run)
        if isinstance(pending, dict) and pending.get("approval_id") is not None:
            body["approval_id"] = str(pending["approval_id"])
    if kind == "fanout":
        from ar_domain.research.engine import pending_subtasks, state_of  # noqa: PLC0415

        body["subtasks"] = pending_subtasks(state_of(run, text))
    return body

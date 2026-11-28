"""One step of a chat turn: a model call or a single tool call."""

import asyncio
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
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(store)
    await reload_run(store, run_id)
    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict):
        return {"status": "missing", "kind": "final", "run_id": str(run_id)}
    during_tool = False
    try:
        async with heartbeating():
            during_tool = True
            stopped = await _stop_or_apply(store, run, run_id, payload)
            during_tool = False
            if stopped is not None:
                await flush_store(store)
                return stopped
            return await _advance(store, run, run_id, payload, runs)
    except asyncio.CancelledError:
        # A stop while the model is writing cancels the run and keeps the text.
        # A stop during the approved tool call is the deadline cutting it off:
        # that is a failed tool call, not a silent cancel.
        from ar_domain.tools.resume import (  # noqa: PLC0415
            fail_cut_off,
            fail_interrupted_tool,
            mark_cancelled,
        )

        stopped_run = runs.get(run_id) if isinstance(runs, dict) else None
        if isinstance(stopped_run, dict):
            asked = stopped_run.get("cancel_requested") is True
            cut_off = _cut_off_reason()
            if during_tool and not asked:
                fail_interrupted_tool(store, stopped_run)
            elif cut_off and not asked:
                # Temporal stopped the step: it missed its heartbeat or deadline, or the
                # worker is shutting down. Nobody pressed Stop.
                fail_cut_off(store, stopped_run, cut_off)
            else:
                mark_cancelled(store, stopped_run)
        await asyncio.shield(flush_store(store))
        raise


async def _advance(
    store: Any,
    run: dict[str, Any],
    run_id: uuid.UUID,
    payload: dict[str, Any],
    runs: object,
) -> dict[str, Any]:
    """One model or tool step, after a stored decision has been applied."""
    from ar_domain.conversations.logic import run_is_active  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

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
    _keep_results(run, payload.get("results"))
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
    advance = store.advance_turn
    kind = await advance(run_id, text, names)
    await flush_store(store)
    run = runs.get(run_id, {}) if isinstance(runs, dict) else {}
    status = str(run.get("status") or "completed") if isinstance(run, dict) else "completed"
    if not run_is_active(status):
        kind = "final"
    return _step_body(run if isinstance(run, dict) else {}, status, str(kind), str(run_id), text)


def _keep_results(run: dict[str, Any], results: object) -> None:
    """Store what the last fan-out's research sub-tasks found, all of it in one write."""
    if isinstance(results, dict):
        from ar_domain.research.driver import store_results  # noqa: PLC0415

        store_results(run, results)


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
    from ar_common.offload import run_sync  # noqa: PLC0415

    # The approved call waits on the gateway. Under run_sync that wait leaves the
    # loop free, so the activity heartbeat keeps running for the tool's timeout.
    # The limit is the extract budget plus grace: a shorter cap would cancel a long
    # extract, and a tool with a shorter timeout still ends on its own HTTP wait.
    from ar_domain.tools.pipeline import caller_wait_s  # noqa: PLC0415
    from ar_domain.tools.resume import apply_decision  # noqa: PLC0415

    applied = await run_sync(
        apply_decision,
        store,
        run,
        decision,
        limit_s=caller_wait_s({"qualified_name": "documents.extract"}),
    )
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
    if kind == "agents":
        started = run.get("agent_children")
        body["children"] = started if isinstance(started, list) else []
        width = run.get("agent_parallel")
        body["parallel"] = width if isinstance(width, int) and width > 0 else 1
    if kind == "sections":
        batch = run.get("section_batch")
        body["sections"] = batch if isinstance(batch, list) else []
    return body


def _cut_off_reason() -> str:
    """Why Temporal cancelled this activity, when it was not a cancel someone asked for."""
    try:
        details = activity.cancellation_details()
    except RuntimeError:
        return ""
    if details is None or details.cancel_requested:
        return ""
    if details.timed_out:
        return "step_timeout"
    if details.worker_shutdown:
        return "worker_shutdown"
    return ""

"""Submit persisted routines to the local Temporal cluster."""

import asyncio
from typing import TYPE_CHECKING

from temporalio.client import (
    Client,
    ScheduleAlreadyRunningError,
    ScheduleUpdate,
)
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from ar_common.errors import UnavailableError
from ar_domain.durable.after import after_commit
from ar_domain.durable.flush import flush_store
from ar_domain.routines.clock import build_schedule
from ar_domain.routines.engine import close_delivery, turn_payload

if TYPE_CHECKING:
    import uuid
    from typing import Any

    from ar_domain.chat.service import ChatBehaviour


def delivery_decided(store: Any, approval: dict[str, object]) -> None:
    """Act on a decided delivery. An approved one is sent by a worker, not by this process.

    A refused, withdrawn or expired one is recorded and nothing is sent. With no workflow
    engine the approval is refused in words rather than recorded as sent.
    """
    if approval.get("status") != "approved":
        close_delivery(store, approval)
        return
    start = getattr(getattr(store, "temporal_client", None), "start_workflow", None)
    if not callable(start):
        raise UnavailableError("Delivery is unavailable. Please try again.")
    approval_id = str(approval.get("id") or "")

    async def _start() -> None:
        try:
            await start(
                "RoutineDeliveryWorkflow",
                {"approval_id": approval_id},
                id=f"routine-delivery-{approval_id}",
                task_queue="ar-system",
            )
        except WorkflowAlreadyStartedError:
            return

    def _go() -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_start())
            return
        task = loop.create_task(_start())
        tasks = getattr(store, "tasks", None)
        if isinstance(tasks, list):
            tasks.append(task)

    after_commit(store, _go)


def client_for(store: ChatBehaviour) -> Client:
    client = store.temporal_client
    if not isinstance(client, Client):
        raise UnavailableError("Routine execution is unavailable. Please try again.")
    return client


async def start_run(store: ChatBehaviour, run_id: uuid.UUID) -> None:
    """The accepted event and complete message skeleton commit before dispatch."""
    client = client_for(store)
    run = store.runs[run_id]
    event = next(row for row in store.routine_events.values() if row.get("run_id") == run_id)
    await flush_store(store)
    try:
        await client.start_workflow(
            "RoutineRunWorkflow",
            {
                "routine_id": str(run["routine_id"]),
                "event_id": str(event["id"]),
                "run_id": str(run_id),
                "workflow": turn_payload(store, run),
            },
            id=f"routine-event-{event['id']}",
            task_queue="ar-system",
        )
    except RPCError as exc:
        raise UnavailableError("Routine execution is unavailable. Please try again.") from exc


async def sync_schedule(
    store: ChatBehaviour, routine_id: uuid.UUID, *, deleted: bool = False
) -> None:
    """Apply creation, edits and pause/resume to the actual Temporal schedule."""
    if store.durable_engine is None:
        return
    client = client_for(store)
    schedule_id = f"routine-{routine_id}"
    handle = client.get_schedule_handle(schedule_id)
    row = store.routines.get(routine_id)
    if deleted or row is None or row.get("trigger_type") != "schedule":
        try:
            await handle.delete()
        except RPCError as exc:
            if exc.status != RPCStatusCode.NOT_FOUND:
                raise
        return
    schedule = build_schedule(row)
    await flush_store(store)
    try:
        await client.create_schedule(schedule_id, schedule)
    except ScheduleAlreadyRunningError:
        await handle.update(lambda _: ScheduleUpdate(schedule=schedule))

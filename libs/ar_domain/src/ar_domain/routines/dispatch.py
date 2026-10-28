"""Submit persisted routines to the local Temporal cluster."""

from datetime import timedelta
from typing import TYPE_CHECKING

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
)
from temporalio.service import RPCError, RPCStatusCode

from ar_common.errors import UnavailableError
from ar_domain.durable.flush import flush_store

if TYPE_CHECKING:
    import uuid

    from ar_domain.chat.service import ChatService


def client_for(store: ChatService) -> Client:
    client = store.temporal_client
    if not isinstance(client, Client):
        raise UnavailableError("Routine execution is unavailable. Please try again.")
    return client


async def start_run(store: ChatService, run_id: uuid.UUID) -> None:
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
            },
            id=f"routine-event-{event['id']}",
            task_queue="ar-system",
        )
    except RPCError as exc:
        raise UnavailableError("Routine execution is unavailable. Please try again.") from exc


async def sync_schedule(
    store: ChatService, routine_id: uuid.UUID, *, deleted: bool = False
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
    raw_config = row.get("trigger_config")
    config = raw_config if isinstance(raw_config, dict) else {}
    overlap = {
        "skip": ScheduleOverlapPolicy.SKIP,
        "buffer_one": ScheduleOverlapPolicy.BUFFER_ONE,
        "allow": ScheduleOverlapPolicy.ALLOW_ALL,
    }[str(row.get("concurrency_policy") or "skip")]
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            "RoutineRunWorkflow",
            {"routine_id": str(routine_id), "source": "schedule"},
            id=f"routine-fire-{routine_id}",
            task_queue="ar-system",
        ),
        spec=ScheduleSpec(
            cron_expressions=[str(config["cron"])],
            time_zone_name=str(config.get("timezone") or "UTC"),
            jitter=timedelta(seconds=int(config.get("jitter_s") or 0)),
        ),
        policy=SchedulePolicy(overlap=overlap),
        state=ScheduleState(paused=row.get("status") != "active"),
    )
    await flush_store(store)
    try:
        await client.create_schedule(schedule_id, schedule)
    except ScheduleAlreadyRunningError:
        await handle.update(lambda _: ScheduleUpdate(schedule=schedule))

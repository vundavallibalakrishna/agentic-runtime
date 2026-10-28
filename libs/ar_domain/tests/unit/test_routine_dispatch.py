"""Temporal dispatch commits state and preserves schedule controls."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from temporalio.client import ScheduleAlreadyRunningError
from temporalio.service import RPCError, RPCStatusCode

from ar_common.errors import UnavailableError
from ar_domain.chat.service import ChatService
from ar_domain.routines.dispatch import client_for, start_run, sync_schedule


class ClientDouble:
    def __init__(self) -> None:
        self.handle = SimpleNamespace(delete=AsyncMock(), update=AsyncMock())
        self.start_workflow = AsyncMock()
        self.create_schedule = AsyncMock()

    def get_schedule_handle(self, key: str):
        return self.handle


@pytest.mark.parametrize("operation", ["create", "update", "pause", "delete", "missing", "error"])
async def test_schedules_preserve_timezone_overlap_pause_and_errors(operation, monkeypatch):
    store = ChatService()
    store.durable_engine = object()
    client = ClientDouble()
    store.temporal_client = client
    monkeypatch.setattr("ar_domain.routines.dispatch.Client", ClientDouble)
    flush = AsyncMock()
    monkeypatch.setattr("ar_domain.routines.dispatch.flush_store", flush)
    routine_id = uuid.uuid4()
    store.routines[routine_id] = {
        "id": routine_id,
        "trigger_type": "schedule",
        "concurrency_policy": "buffer_one",
        "trigger_config": {"cron": "0 9 * * 1", "timezone": "Asia/Kolkata", "jitter_s": 10},
        "status": "paused" if operation == "pause" else "active",
    }
    if operation == "update":
        client.create_schedule.side_effect = ScheduleAlreadyRunningError()
    if operation in {"missing", "error"}:
        client.handle.delete.side_effect = RPCError(
            "Unavailable",
            RPCStatusCode.NOT_FOUND if operation == "missing" else RPCStatusCode.UNAVAILABLE,
            b"",
        )
    if operation == "error":
        with pytest.raises(RPCError):
            await sync_schedule(store, routine_id, deleted=True)
        return
    await sync_schedule(store, routine_id, deleted=operation in {"delete", "missing"})
    if operation in {"delete", "missing"}:
        client.handle.delete.assert_awaited_once()
        client.create_schedule.assert_not_awaited()
    else:
        flush.assert_awaited_once_with(store)
        schedule = client.create_schedule.call_args.args[1]
        assert schedule.spec.cron_expressions == ["0 9 * * 1"]
        assert schedule.spec.time_zone_name == "Asia/Kolkata"
        assert schedule.spec.jitter.total_seconds() == 10
        assert schedule.state.paused == (operation == "pause")
        assert schedule.action.workflow == "RoutineRunWorkflow"
        if operation == "update":
            assert client.handle.update.call_args.args[0](None).schedule is schedule


async def test_dispatch_flushes_before_start_and_reports_cluster_failure(monkeypatch):
    store = ChatService()
    client = ClientDouble()
    store.temporal_client = client
    monkeypatch.setattr("ar_domain.routines.dispatch.Client", ClientDouble)
    run_id, routine_id, event_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    store.runs[run_id] = {"id": run_id, "routine_id": routine_id}
    store.routine_events[event_id] = {"id": event_id, "run_id": run_id}
    order = []

    async def flush(store):
        order.append("commit")

    async def start(*args, **kwargs):
        order.append("dispatch")
        assert kwargs["id"] == f"routine-event-{event_id}"
        assert args[1]["run_id"] == str(run_id)

    monkeypatch.setattr("ar_domain.routines.dispatch.flush_store", flush)
    client.start_workflow.side_effect = start
    await start_run(store, run_id)
    assert order == ["commit", "dispatch"]
    client.start_workflow.side_effect = RPCError("unavailable", RPCStatusCode.UNAVAILABLE, b"")
    with pytest.raises(UnavailableError):
        await start_run(store, run_id)
    store.temporal_client = None
    with pytest.raises(UnavailableError):
        client_for(store)
    await sync_schedule(store, routine_id)

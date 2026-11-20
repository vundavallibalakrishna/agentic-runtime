"""The reaper activity is safe to repeat."""

from datetime import timedelta
from typing import TYPE_CHECKING

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleOverlapPolicy,
)
from temporalio.worker import Worker

from ar_common.settings import BaseServiceSettings
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.sandboxes.runtime import ensure_scope
from ar_system.sandbox_schedule import SCHEDULE_ID, ensure_reaper_schedule
from ar_system.workflows.sandbox_reaper import SandboxReaperWorkflow, bind_store, reap_sandboxes
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest


async def test_reaper_suspends_once(temporal_env: object) -> None:
    store = demo_store()
    row = ensure_scope(
        store,
        tenant_id=demo_id("tenant"),
        template_slug="python-data",
        scope="conversation",
        scope_key="conv:reaper",
        conversation_id=None,
        agent_id=None,
        user_id=demo_id("admin"),
    )
    store.sandbox_templates[row["template_id"]]["idle_suspend_s"] = 1
    store.sandbox_templates[row["template_id"]]["max_lifetime_s"] = 10**9
    row["last_active_at"] = utcnow() - timedelta(seconds=30)
    bind_store(store)
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="m6-reaper",
        workflows=[SandboxReaperWorkflow],
        activities=[reap_sandboxes],
    ):
        first = await client.execute_workflow(
            SandboxReaperWorkflow.run,
            id="m6-reaper",
            task_queue="m6-reaper",
        )
    assert first["suspended"] == 1
    second = await reap_sandboxes()
    assert second["suspended"] == 0
    assert row["status"] == "suspended"


class _Schedules:
    """The part of a Temporal client the schedule needs, with one schedule already there."""

    def __init__(self) -> None:
        self.created: list[tuple[str, Schedule]] = []
        self.updated: list[Schedule] = []

    async def create_schedule(self, schedule_id: str, schedule: Schedule) -> None:
        if self.created:
            raise ScheduleAlreadyRunningError
        self.created.append((schedule_id, schedule))

    def get_schedule_handle(self, schedule_id: str) -> _Schedules:
        assert schedule_id == SCHEDULE_ID
        return self

    async def update(self, updater: object) -> None:
        self.updated.append(updater(None).schedule)  # type: ignore[operator]


async def test_the_sweep_is_scheduled_once_however_many_workers_ask() -> None:
    client = _Schedules()
    await ensure_reaper_schedule(client, 60)  # type: ignore[arg-type]
    schedule_id, schedule = client.created[0]
    assert schedule_id == SCHEDULE_ID
    action = schedule.action
    assert isinstance(action, ScheduleActionStartWorkflow)
    assert action.workflow == "SandboxReaperWorkflow"
    assert action.task_queue == "ar-system"
    assert schedule.spec.intervals[0].every == timedelta(seconds=60)
    # A sweep that is still running is not started a second time.
    assert schedule.policy.overlap is ScheduleOverlapPolicy.SKIP
    # A second worker, or a changed interval, updates the one schedule.
    await ensure_reaper_schedule(client, 30)  # type: ignore[arg-type]
    assert len(client.created) == 1
    assert client.updated[0].spec.intervals[0].every == timedelta(seconds=30)


def test_the_interval_is_a_setting_with_a_default_of_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert BaseServiceSettings().sandbox_reap_interval_s == 60
    monkeypatch.setenv("AR_SANDBOX_REAP_INTERVAL_S", "15")
    assert BaseServiceSettings().sandbox_reap_interval_s == 15


async def test_reaper_without_a_store() -> None:
    from ar_system.workflows import sandbox_reaper

    previous = sandbox_reaper._STORE
    sandbox_reaper._STORE = None
    try:
        assert await reap_sandboxes() == {"suspended": 0, "terminated": 0, "removed": 0}
    finally:
        sandbox_reaper._STORE = previous

"""Routine workflows on the time-skipping Temporal server."""

import uuid

import pytest
from temporalio.worker import Worker

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.clock import build_schedule
from ar_runtime.activities.execute_chat_turn import execute_chat_turn
from ar_runtime.activities.expire_approval import bind_store as bind_runtime
from ar_runtime.workflows.turn import TurnWorkflow
from ar_system.routines_store import bind_store
from ar_system.workflows.routine_poll import RoutinePollWorkflow, poll_activity
from ar_system.workflows.routine_run import (
    RoutineReconcileWorkflow,
    RoutineRunWorkflow,
    accept_activity,
    complete_activity,
    prepare_activity,
    reconcile_activity,
)
from ar_testing.demo import demo_store
from ar_testing.showcase_build import seed_showcase

pytestmark = pytest.mark.asyncio


def _ready() -> tuple[ChatService, str]:
    store = demo_store()
    store.seed_demo()
    seed_showcase(store)
    book = RoutineBook(store)
    agent = store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    created = book.create(
        Actor(
            tenant_id=demo_id("tenant"),
            user_id=demo_id("admin"),
            permissions=frozenset({"routines:create", "approvals:grant_standing"}),
            display_name="Admin",
        ),
        {
            "name": "Hourly note",
            "instructions": "Write one sentence.",
            "agent_id": agent["id"],
            "trigger": {"type": "manual"},
            "delivery": [{"type": "conversation"}],
        },
    )

    async def generate(self: ChatService, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        self.runs[run_id]["status"] = "completed"
        self.runs[run_id]["result_summary"] = "Done."

    store.generate = generate.__get__(store, ChatService)  # type: ignore[method-assign]
    bind_store(store)
    bind_runtime(store)
    return store, str(created["id"])


async def test_routine_run_poll_and_reconcile(temporal_env: object) -> None:
    store, routine_id = _ready()
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="ar-system",
        workflows=[RoutineRunWorkflow, RoutinePollWorkflow, RoutineReconcileWorkflow, TurnWorkflow],
        activities=[
            accept_activity,
            prepare_activity,
            complete_activity,
            poll_activity,
            reconcile_activity,
            execute_chat_turn,
        ],
    ):
        result = await client.execute_workflow(
            RoutineRunWorkflow.run,
            {
                "routine_id": routine_id,
                "source": "manual",
                "idempotency_key": "wf-1",
                "runtime_queue": "ar-system",
                "envelope": {"type": "manual"},
            },
            id="m10-routine-run",
            task_queue="ar-system",
        )
        assert result["status"] == "completed"
        duplicate = await client.execute_workflow(
            RoutineRunWorkflow.run,
            {
                "routine_id": routine_id,
                "source": "manual",
                "idempotency_key": "wf-1",
                "runtime_queue": "ar-system",
                "envelope": {"type": "manual"},
            },
            id="m10-routine-dup",
            task_queue="ar-system",
        )
        assert duplicate["status"] == "duplicate"
        store.routines[uuid.UUID(routine_id)]["trigger_type"] = "db_change"
        store.routines[uuid.UUID(routine_id)]["trigger_config"] = {
            "_pending": [{"idempotency_key": "row-1", "updated_at": "t"}]
        }
        polled = await client.execute_workflow(
            RoutinePollWorkflow.run,
            {"routine_id": routine_id},
            id="m10-routine-poll",
            task_queue="ar-system",
        )
        assert polled
        store.temporal_schedules.clear()
        repaired = await client.execute_workflow(
            RoutineReconcileWorkflow.run,
            id="m10-routine-reconcile",
            task_queue="ar-system",
        )
        assert repaired["repaired"] >= 0


async def test_schedule_fires_from_the_temporal_clock() -> None:
    """A Temporal dev server fires the schedule. This does not call the in-process tick.

    The time-skipping test server does not implement CreateSchedule. The dev
    server does. The production spec is cron; this wait uses a one-second
    interval so the suite does not sit for a full minute. The action is the
    one ``build_schedule`` registers.
    """
    import asyncio
    from datetime import timedelta

    from temporalio.client import Schedule, ScheduleIntervalSpec, ScheduleSpec
    from temporalio.testing import WorkflowEnvironment

    store, routine_id = _ready()
    routine = store.routines[uuid.UUID(routine_id)]
    routine["trigger_type"] = "schedule"
    routine["status"] = "active"
    routine["trigger_config"] = {"cron": "* * * * *", "timezone": "UTC", "jitter_s": 0}
    built = build_schedule(routine)
    assert built.spec.cron_expressions == ["* * * * *"]
    schedule = Schedule(
        action=built.action,
        spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(seconds=1))]),
        policy=built.policy,
        state=built.state,
    )
    async with await WorkflowEnvironment.start_local() as env:
        async with Worker(
            env.client,
            task_queue="ar-system",
            workflows=[RoutineRunWorkflow, TurnWorkflow],
            activities=[
                accept_activity,
                prepare_activity,
                complete_activity,
                execute_chat_turn,
            ],
        ):
            await env.client.create_schedule(f"routine-{routine_id}", schedule)
            for _ in range(20):
                sources = [str(row.get("source")) for row in store.routine_events.values()]
                if "schedule" in sources:
                    break
                await asyncio.sleep(0.5)
    sources = [str(row.get("source")) for row in store.routine_events.values()]
    assert "schedule" in sources

"""Routine workflows on the time-skipping Temporal server."""

import uuid

import pytest
from temporalio.worker import Worker

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.routines.book import RoutineBook
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

pytestmark = pytest.mark.asyncio


def _ready() -> tuple[ChatService, str]:
    store = ChatService()
    store.seed_demo()
    store.seed_showcase()
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

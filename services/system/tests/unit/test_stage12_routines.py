"""An agent creates a routine, a Temporal schedule fires, and a bad webhook is rejected.

Proof: contract. The model is the in-process stand-in.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
)
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.routines.signature import header_for
from ar_domain.tools.handlers import dispatch
from ar_domain.tools.seed_tools import seed
from ar_runtime.activities.advance_chat_step import advance_chat_step
from ar_runtime.activities.execute_chat_turn import execute_chat_turn
from ar_runtime.activities.expire_approval import bind_store as bind_runtime
from ar_runtime.workflows.turn import TurnWorkflow
from ar_system.routines_store import bind_store
from ar_system.workflows.routine_run import (
    RoutineRunWorkflow,
    accept_activity,
    complete_activity,
    prepare_activity,
)
from ar_testing.demo import demo_application, demo_store


def _store() -> tuple[ChatService, dict[str, object]]:
    store = demo_store()
    seed(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")

    async def generate(self: ChatService, run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        self.runs[run_id]["status"] = "completed"
        self.runs[run_id]["result_summary"] = "routine output"

    async def advance_turn(
        self: ChatService, run_id: uuid.UUID, text: str, names: list[str]
    ) -> str:
        await generate(self, run_id, text, names)
        return "final"

    store.generate = generate.__get__(store, ChatService)
    store.advance_turn = advance_turn.__get__(store, ChatService)
    agent_id = next(row["id"] for row in store.agents.values() if row.get("tenant_id") == tenant)
    created = dispatch(
        store,
        "builtin://routines",
        "create",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "name": "Hourly note",
            "instructions": "Write one sentence.",
            "trigger_type": "schedule",
            "cron": "0 * * * *",
            "timezone": "UTC",
            "agent_id": agent_id,
        },
        "",
    )
    assert created["is_error"] is False
    bind_store(store)
    bind_runtime(store)
    return store, created["structured"]


async def test_schedule_trigger_runs_and_records_output() -> None:
    store, created = _store()
    routine_id = str(created["id"])
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
                advance_chat_step,
            ],
        ):
            schedule = Schedule(
                action=ScheduleActionStartWorkflow(
                    RoutineRunWorkflow.run,
                    {
                        "routine_id": routine_id,
                        "source": "schedule",
                        "idempotency_key": "stage12-tick",
                        "runtime_queue": "ar-system",
                        "envelope": {"type": "schedule"},
                    },
                    id=f"stage12-run-{routine_id}",
                    task_queue="ar-system",
                ),
                spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=timedelta(hours=1))]),
            )
            await env.client.create_schedule(f"stage12-{routine_id}", schedule)
            await env.client.get_schedule_handle(f"stage12-{routine_id}").trigger()
            for _ in range(40):
                events = list(store.routine_events.values())
                if any(row.get("status") == "completed" for row in events):
                    break
                await asyncio.sleep(0.25)
    events = list(store.routine_events.values())
    assert any(row.get("source") == "schedule" for row in events)
    assert any(
        row.get("status") == "completed" and row.get("result_summary") == "routine output"
        for row in store.runs.values()
    )


def test_webhook_signature_accepts_and_rejects() -> None:
    store = demo_store()
    seed(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")
    agent_id = next(row["id"] for row in store.agents.values() if row.get("tenant_id") == tenant)
    created = dispatch(
        store,
        "builtin://routines",
        "create",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "name": "Inbound",
            "instructions": "Read the event.",
            "trigger_type": "webhook",
            "agent_id": agent_id,
        },
        "",
    )
    assert created["is_error"] is False
    webhook = created["structured"]["webhook"]
    token = str(webhook["webhook_url"]).rsplit("/", 1)[-1]
    secret = str(webhook["webhook_secret"])
    app = demo_application()
    app.state.chat = store
    client = TestClient(app)
    body = b'{"ticket":1}'
    bad = client.post(f"/api/v1/hooks/routines/{token}", content=body)
    assert bad.status_code == 401
    signed = client.post(
        f"/api/v1/hooks/routines/{token}",
        content=body,
        headers={"X-AR-Signature": header_for(secret, body, int(__import__("time").time()))},
    )
    assert signed.status_code == 202
    assert PERMISSION_KEYS

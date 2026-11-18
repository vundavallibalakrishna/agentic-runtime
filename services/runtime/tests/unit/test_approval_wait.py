"""Approval and input resume are signals on AgentRunWorkflow."""

import asyncio
import uuid
from typing import Any

import pytest
from temporalio import activity
from temporalio.worker import Worker

from ar_runtime.workflows.agent_run import turn_workflow
from ar_runtime.workflows.turn import TurnWorkflow

pytestmark = pytest.mark.asyncio


async def test_approval_and_input_signals_continue_the_run(temporal_env: object) -> None:
    assert turn_workflow() is TurnWorkflow
    seen: list[dict[str, object]] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        if len(seen) == 1:
            return {
                "run_id": str(payload["run_id"]),
                "status": "waiting_approval",
                "kind": "paused",
                "approval_id": "a1",
            }
        if len(seen) == 2:
            assert payload.get("decision") == {"status": "approved", "approval_id": "a1"}
            return {
                "run_id": str(payload["run_id"]),
                "status": "waiting_input",
                "kind": "paused",
            }
        assert payload.get("decision") == {"status": "input", "text": "blue"}
        return {"run_id": str(payload["run_id"]), "status": "completed", "kind": "final"}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": str(payload.get("status") or "failed")}

    client = temporal_env.client  # type: ignore[attr-defined]
    queue = f"approval-{uuid.uuid4()}"
    async with Worker(
        client, task_queue=queue, workflows=[TurnWorkflow], activities=[step, finish]
    ):
        handle = await client.start_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True, "max_steps": 8, "history_steps": 8},
            id=queue,
            task_queue=queue,
        )
        await handle.signal(
            TurnWorkflow.approval_decided, {"status": "approved", "approval_id": "a1"}
        )
        await handle.signal(TurnWorkflow.user_input, {"text": "blue"})
        result = await handle.result()
    assert result["status"] == "completed"
    assert len(seen) == 3


async def test_a_rejected_approval_stops_the_run(temporal_env: object) -> None:
    finished: list[str] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("decision"):
            assert payload["decision"] == {"status": "rejected"}
            return {"run_id": str(payload["run_id"]), "status": "completed", "kind": "final"}
        return {"run_id": str(payload["run_id"]), "status": "waiting_approval", "kind": "paused"}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        finished.append(str(payload.get("status")))
        return {"status": str(payload.get("status"))}

    client = temporal_env.client  # type: ignore[attr-defined]
    queue = f"reject-{uuid.uuid4()}"
    async with Worker(
        client, task_queue=queue, workflows=[TurnWorkflow], activities=[step, finish]
    ):
        handle = await client.start_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True},
            id=queue,
            task_queue=queue,
        )
        await handle.signal(TurnWorkflow.approval_decided, {"status": "rejected"})
        result = await handle.result()
    assert result["status"] == "completed"
    assert finished == []


async def test_cancel_during_steps_stops_the_workflow(temporal_env: object) -> None:
    started = asyncio.Event()

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        started.set()
        while True:
            activity.heartbeat()
            await asyncio.sleep(0.05)

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": str(payload.get("status") or "failed"), "run_id": payload.get("run_id")}

    client = temporal_env.client  # type: ignore[attr-defined]
    queue = f"cancel-steps-{uuid.uuid4()}"
    async with Worker(
        client, task_queue=queue, workflows=[TurnWorkflow], activities=[step, finish]
    ):
        handle = await client.start_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True, "max_steps": 4},
            id=queue,
            task_queue=queue,
        )
        await asyncio.wait_for(started.wait(), 10)
        await handle.signal(TurnWorkflow.cancel)
        result = await handle.result()
    assert result["status"] == "cancelled"

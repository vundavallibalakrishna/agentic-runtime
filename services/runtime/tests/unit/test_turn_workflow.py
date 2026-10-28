"""The turn workflow records failure and waits for cancellation before finishing."""

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from ar_runtime.workflows.turn import TurnWorkflow

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment


@pytest.mark.parametrize("outcome", ["completed", "failed", "cancelled"])
async def test_turn_finishes_or_cancels(temporal_env: WorkflowEnvironment, outcome: str) -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()
    finished = []

    @activity.defn(name="execute_chat_turn")
    async def turn(payload: dict[str, str]) -> dict[str, str]:
        started.set()
        if outcome == "failed":
            raise ApplicationError("upstream failure", non_retryable=True)
        if outcome == "cancelled":
            try:
                while True:
                    activity.heartbeat()
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                cancelled.set()
                raise
        return {"run_id": payload["run_id"], "status": "completed"}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, str]) -> dict[str, str]:
        if outcome == "cancelled":
            assert cancelled.is_set(), "The generator must stop before terminal state is saved"
        finished.append(payload["status"])
        return payload

    queue = f"test-turn-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client, task_queue=queue, workflows=[TurnWorkflow], activities=[turn, finish]
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run, {"run_id": str(uuid.uuid4())}, id=queue, task_queue=queue
        )
        await asyncio.wait_for(started.wait(), 10)
        if outcome == "cancelled":
            await handle.signal(TurnWorkflow.cancel)
        result = await handle.result()
    assert result["status"] == outcome
    assert finished == ([] if outcome == "completed" else [outcome])

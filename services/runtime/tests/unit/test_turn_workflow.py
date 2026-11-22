"""The turn workflow records failure and waits for cancellation before finishing."""

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from temporalio import activity
from temporalio.api.enums.v1 import EventType
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


async def test_step_workflow_runs_one_activity_per_step(temporal_env: WorkflowEnvironment) -> None:
    """A stepped turn calls the step activity once per model or tool step. Proof: unit."""
    seen: list[int] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, str]) -> dict[str, str]:
        seen.append(1)
        kind = "tools" if len(seen) == 1 else "final"
        return {
            "run_id": str(payload["run_id"]),
            "status": "running" if kind == "tools" else "completed",
            "kind": kind,
        }

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, str]) -> dict[str, str]:
        return payload

    queue = f"test-steps-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client,
        task_queue=queue,
        workflows=[TurnWorkflow],
        activities=[step, finish],
    ):
        result = await temporal_env.client.execute_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True},
            id=queue,
            task_queue=queue,
        )
    assert result["status"] == "completed"
    assert len(seen) == 2


async def test_a_long_run_continues_as_new(temporal_env: WorkflowEnvironment) -> None:
    """History is capped by ``history_steps``. The run budget is ``max_steps``."""
    seen: list[int] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, str]) -> dict[str, str]:
        seen.append(1)
        kind = "final" if len(seen) >= 5 else "model"
        status = "completed" if kind == "final" else "running"
        return {"run_id": str(payload["run_id"]), "status": status, "kind": kind}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, str]) -> dict[str, str]:
        return payload

    queue = f"test-continue-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client,
        task_queue=queue,
        workflows=[TurnWorkflow],
        activities=[step, finish],
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {
                "run_id": str(uuid.uuid4()),
                "steps": True,
                "max_steps": 8,
                "history_steps": 2,
                "step_timeout_s": 660,
            },
            id=queue,
            task_queue=queue,
        )
        result = await handle.result()
        history = await handle.fetch_history()
    assert result["status"] == "completed"
    assert len(seen) == 5
    started = next(
        event
        for event in history.events
        if event.event_type == EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED
    )
    continued_from = started.workflow_execution_started_event_attributes.continued_execution_run_id
    assert continued_from
    # A step may take what the starter allowed, in the continued execution too.
    allowed = [
        event.activity_task_scheduled_event_attributes.start_to_close_timeout.seconds
        for event in history.events
        if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED
        and event.activity_task_scheduled_event_attributes.activity_type.name == "advance_chat_step"
    ]
    assert allowed
    assert set(allowed) == {660}


async def test_fanout_timeout_and_cancel_while_waiting(temporal_env: WorkflowEnvironment) -> None:
    """A fan-out step runs sub-tasks, then an unanswered wait expires."""
    subtasks: list[str] = []
    handed: list[object] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        handed.append(payload.get("results"))
        decision = payload.get("decision")
        if isinstance(decision, dict):
            return {
                "run_id": str(payload["run_id"]),
                "status": "completed",
                "kind": "final",
                "saw": decision["status"],
            }
        if not subtasks:
            return {
                "run_id": str(payload["run_id"]),
                "status": "running",
                "kind": "fanout",
                "subtasks": [{"id": "1", "text": "kites"}, "skip-me"],
            }
        return {
            "run_id": str(payload["run_id"]),
            "status": "waiting_approval",
            "kind": "paused",
            "approval_id": "a",
        }

    @activity.defn(name="research_subtask")
    async def subtask(payload: dict[str, Any]) -> dict[str, Any]:
        subtasks.append(str(payload.get("id")))
        return {"status": "done"}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": str(payload.get("status") or "failed")}

    queue = f"test-fanout-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client,
        task_queue=queue,
        workflows=[TurnWorkflow],
        activities=[step, subtask, finish],
    ):
        expired = await temporal_env.client.execute_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True, "wait_s": 1, "max_steps": 6},
            id=queue,
            task_queue=queue,
        )
    assert subtasks == ["1"]
    assert expired["status"] == "completed"
    # The step after the fan-out is handed what the sub-tasks found, and only that step.
    assert handed == [None, {"1": {"status": "done"}}, None]


async def test_cancel_during_a_wait_and_a_non_dict_result(
    temporal_env: WorkflowEnvironment,
) -> None:
    paused = asyncio.Event()

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        paused.set()
        return {"run_id": str(payload.get("run_id")), "status": "waiting_input", "kind": "paused"}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": str(payload.get("status") or "failed")}

    @activity.defn(name="execute_chat_turn")
    async def whole(_payload: dict[str, Any]) -> str:
        return "not-a-dict"

    queue = f"test-wait-cancel-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client,
        task_queue=queue,
        workflows=[TurnWorkflow],
        activities=[step, finish, whole],
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True, "wait_s": 30},
            id=queue,
            task_queue=queue,
        )
        await asyncio.wait_for(paused.wait(), 10)
        await asyncio.sleep(0.2)
        await handle.signal(TurnWorkflow.cancel)
        cancelled = await handle.result()
        plain = await temporal_env.client.execute_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4())},
            id=f"{queue}-plain",
            task_queue=queue,
        )
    assert cancelled["status"] == "cancelled"
    assert plain["status"] == "completed"


async def test_history_carries_a_decision_and_an_empty_fanout(
    temporal_env: WorkflowEnvironment,
) -> None:
    seen: list[object] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload.get("decision"))
        if payload.get("decision"):
            return {"run_id": str(payload["run_id"]), "status": "completed", "kind": "final"}
        if len(seen) == 1:
            return {
                "run_id": str(payload["run_id"]),
                "status": "running",
                "kind": "fanout",
                "subtasks": [],
            }
        return {
            "run_id": str(payload["run_id"]),
            "status": "waiting_approval",
            "kind": "paused",
        }

    @activity.defn(name="finish_chat_turn")
    async def finish(_payload: dict[str, Any]) -> str:
        return "not-a-dict"

    queue = f"test-carry-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client,
        task_queue=queue,
        workflows=[TurnWorkflow],
        activities=[step, finish],
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {
                "run_id": str(uuid.uuid4()),
                "steps": True,
                "history_steps": 2,
                "max_steps": 6,
            },
            id=queue,
            task_queue=queue,
        )
        await handle.signal(TurnWorkflow.approval_decided, {"status": "approved"})
        result = await handle.result()
    assert result["status"] == "completed"


async def test_cancel_after_a_step_returns_still_stops(
    temporal_env: WorkflowEnvironment,
) -> None:
    started = asyncio.Event()

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        started.set()
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            return {
                "run_id": str(payload["run_id"]),
                "status": "running",
                "kind": "model",
            }

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": str(payload.get("status") or "failed")}

    queue = f"test-after-step-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client, task_queue=queue, workflows=[TurnWorkflow], activities=[step, finish]
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True, "max_steps": 3},
            id=queue,
            task_queue=queue,
        )
        await asyncio.wait_for(started.wait(), 10)
        await handle.signal(TurnWorkflow.user_input, "blue")
        await handle.signal(TurnWorkflow.cancel)
        result = await handle.result()
    assert result["status"] == "cancelled"


async def test_a_terminal_activity_that_is_not_a_dict_is_failed(
    temporal_env: WorkflowEnvironment,
) -> None:
    @activity.defn(name="advance_chat_step")
    async def step(_payload: dict[str, Any]) -> None:
        raise ApplicationError("upstream", non_retryable=True)

    @activity.defn(name="finish_chat_turn")
    async def finish(_payload: dict[str, Any]) -> str:
        return "not-a-dict"

    queue = f"test-nondict-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client, task_queue=queue, workflows=[TurnWorkflow], activities=[step, finish]
    ):
        result = await temporal_env.client.execute_workflow(
            TurnWorkflow.run,
            {"run_id": str(uuid.uuid4()), "steps": True, "max_steps": 2},
            id=queue,
            task_queue=queue,
        )
    assert result["status"] == "failed"

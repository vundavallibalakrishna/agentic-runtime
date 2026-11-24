"""A call to other agents runs each as a child AgentRunWorkflow, and Stop reaches them."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from temporalio import activity
from temporalio.worker import Worker

from ar_runtime.workflows.turn import TurnWorkflow

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment

_QUEUE = "called-agents"


def _child(run_id: str) -> dict[str, Any]:
    return {"run_id": run_id, "steps": True, "max_steps": 4, "text": "task"}


@activity.defn(name="finish_chat_turn")
async def _finish(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": payload.get("status") or "completed", "run_id": payload.get("run_id")}


async def test_called_agents_run_as_child_workflows_before_the_caller_goes_on(
    temporal_env: WorkflowEnvironment,
) -> None:
    order: list[str] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id"))
        order.append(run_id)
        if run_id == "lead" and order.count("lead") == 1:
            return {
                "status": "running",
                "kind": "agents",
                "run_id": run_id,
                "children": [_child("one"), _child("two")],
            }
        if run_id != "lead" and order.count(run_id) == 1:
            return {"status": "running", "kind": "model", "run_id": run_id}
        return {"status": "completed", "kind": "final", "run_id": run_id}

    async with Worker(
        temporal_env.client,
        task_queue=_QUEUE,
        workflows=[TurnWorkflow],
        activities=[step, _finish],
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {"run_id": "lead", "steps": True, "max_steps": 8},
            id="run-lead",
            task_queue=_QUEUE,
        )
        result = await handle.result()
        # Each called agent is the run workflow under the id every signal is sent to.
        for run_id in ("one", "two"):
            ended = await temporal_env.client.get_workflow_handle(f"run-{run_id}").result()
            assert ended["status"] == "completed"
    assert result["status"] == "completed"
    # The caller's second step comes after both of its agents have taken all of theirs.
    assert order[0] == "lead"
    assert order[-1] == "lead"
    assert sorted(order[1:-1]) == ["one", "one", "two", "two"]


async def test_stopping_the_caller_stops_the_agents_it_called(
    temporal_env: WorkflowEnvironment,
) -> None:
    working = asyncio.Event()
    finished: list[tuple[str, str]] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id"))
        if run_id == "lead":
            return {
                "status": "running",
                "kind": "agents",
                "run_id": run_id,
                "children": [_child("slow")],
            }
        working.set()
        while True:
            activity.heartbeat()
            await asyncio.sleep(0.1)

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        finished.append((str(payload.get("run_id")), str(payload.get("status"))))
        return {"status": payload.get("status"), "run_id": payload.get("run_id")}

    async with Worker(
        temporal_env.client,
        task_queue=_QUEUE,
        workflows=[TurnWorkflow],
        activities=[step, finish],
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {"run_id": "lead", "steps": True, "max_steps": 8},
            id="run-lead-stopped",
            task_queue=_QUEUE,
        )
        await asyncio.wait_for(working.wait(), 10)
        await handle.signal(TurnWorkflow.cancel)
        result = await handle.result()
        child = await temporal_env.client.get_workflow_handle("run-slow").result()
    assert result["status"] == "cancelled"
    assert child["status"] == "cancelled"
    # Each run closes itself: the called agent's first, then its caller's.
    assert finished == [("slow", "cancelled"), ("lead", "cancelled")]


async def test_called_agents_past_the_limit_start_as_others_end(
    temporal_env: WorkflowEnvironment,
) -> None:
    going = {"now": 0, "most": 0}
    ran: list[str] = []

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        run_id = str(payload.get("run_id"))
        if run_id == "lead":
            if "lead" in ran:
                return {"status": "completed", "kind": "final", "run_id": run_id}
            ran.append("lead")
            return {
                "status": "running",
                "kind": "agents",
                "run_id": run_id,
                "parallel": 2,
                "children": [_child(f"queued-{at}") for at in range(5)],
            }
        going["now"] += 1
        going["most"] = max(going["most"], going["now"])
        await asyncio.sleep(0.2)
        going["now"] -= 1
        ran.append(run_id)
        return {"status": "completed", "kind": "final", "run_id": run_id}

    async with Worker(
        temporal_env.client,
        task_queue=_QUEUE,
        workflows=[TurnWorkflow],
        activities=[step, _finish],
    ):
        result = await temporal_env.client.execute_workflow(
            TurnWorkflow.run,
            {"run_id": "lead", "steps": True, "max_steps": 8},
            id="run-lead-queued",
            task_queue=_QUEUE,
        )
    assert result["status"] == "completed"
    # All five ran, and never more than two at once.
    assert sorted(ran[1:]) == [f"queued-{at}" for at in range(5)]
    assert going["most"] == 2

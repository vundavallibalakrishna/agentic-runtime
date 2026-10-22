"""Parallel children, cancel, budget and a child approval wait."""

import pytest
from temporalio.client import WorkflowFailureError
from temporalio.worker import Worker

from ar_runtime.activities.create_child_run import create_child_run
from ar_runtime.workflows.agent_run import delegation_workflow
from ar_runtime.workflows.delegation import AgentRunWorkflow, ChildRunWorkflow
from ar_runtime.workflows.turn import TurnWorkflow

pytestmark = pytest.mark.asyncio


def _payload(**extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "run_id": "parent-1",
        "depth": 0,
        "max_depth": 3,
        "remaining_budget": {"max_tokens": 100, "max_steps": 4},
        "allowed": ["researcher"],
        "delegations": [
            {"agent": "researcher", "task": "Research the launch notes."},
            {"agent": "researcher", "task": "Research the rollout plan."},
        ],
    }
    body.update(extra)
    return body


async def test_parallel_children_budget_cancel_and_approval(temporal_env: object) -> None:
    assert delegation_workflow() is AgentRunWorkflow
    definition = AgentRunWorkflow.__temporal_workflow_definition  # type: ignore[attr-defined]
    assert definition.name == "DelegationWorkflow"
    turn = TurnWorkflow.__temporal_workflow_definition  # type: ignore[attr-defined]
    assert turn.name == "AgentRunWorkflow"
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="m9-subagents",
        workflows=[AgentRunWorkflow, ChildRunWorkflow],
        activities=[create_child_run],
    ):
        parallel = await client.execute_workflow(
            AgentRunWorkflow.run,
            _payload(),
            id="m9-parallel",
            task_queue="m9-subagents",
        )
        assert parallel["status"] == "completed"
        assert len(parallel["children"]) == 2
        assert parallel["usage"]["tokens_out"] > 0

        exhausted = await client.execute_workflow(
            AgentRunWorkflow.run,
            _payload(remaining_budget={"max_tokens": 0}, run_id="broke"),
            id="m9-budget",
            task_queue="m9-subagents",
        )
        assert exhausted["status"] == "budget_exceeded"
        assert exhausted["children"] == []

        waiting = await client.start_workflow(
            AgentRunWorkflow.run,
            _payload(
                run_id="approve-me",
                delegations=[
                    {
                        "agent": "researcher",
                        "task": "Wait for a decision.",
                        "wait_approval": True,
                    }
                ],
            ),
            id="m9-approval",
            task_queue="m9-subagents",
        )
        await temporal_env.sleep(1)  # type: ignore[attr-defined]
        child = client.get_workflow_handle("run-approve-me-child-0")
        await child.signal(ChildRunWorkflow.approval_decided, {"status": "approved"})
        approved = await waiting.result()
        assert approved["children"][0]["status"] == "completed"

        cancelled = await client.start_workflow(
            AgentRunWorkflow.run,
            _payload(
                run_id="stop-me",
                delegations=[{"agent": "researcher", "task": "Keep going.", "wait_approval": True}],
            ),
            id="m9-cancel",
            task_queue="m9-subagents",
        )
        await temporal_env.sleep(1)  # type: ignore[attr-defined]
        await cancelled.cancel()
        with pytest.raises(WorkflowFailureError):
            await cancelled.result()

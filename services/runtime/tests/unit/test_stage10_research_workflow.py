"""The research workflow fans out one child and then finishes. Proof: unit."""

from typing import TYPE_CHECKING, Any

from temporalio import activity
from temporalio.worker import Worker

from ar_runtime.workflows.research import ResearchSubtaskWorkflow, ResearchWorkflow

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment


async def test_research_workflow_fans_out_then_finishes(temporal_env: WorkflowEnvironment) -> None:
    seen: list[str] = []

    @activity.defn(name="research_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append("step")
        if len(seen) == 1:
            return {
                "kind": "fanout",
                "status": "running",
                "subtasks": [{"id": "1", "text": "notes"}],
                "run_id": payload.get("run_id"),
            }
        return {"kind": "final", "status": "completed", "run_id": payload.get("run_id")}

    @activity.defn(name="research_subtask")
    async def subtask(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(str(payload.get("id")))
        return {"status": "done"}

    @activity.defn(name="research_cancel")
    async def cancel(payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        return {"status": "cancelled"}

    async with Worker(
        temporal_env.client,
        task_queue="stage10-research",
        workflows=[ResearchWorkflow, ResearchSubtaskWorkflow],
        activities=[step, subtask, cancel],
    ):
        result = await temporal_env.client.execute_workflow(
            ResearchWorkflow.run,
            {"run_id": "run-1"},
            id="stage10-research-run-1",
            task_queue="stage10-research",
        )
    assert result["status"] == "completed"
    assert seen == ["step", "1", "step"]

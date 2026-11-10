"""Research runs as child workflows. One activity is one phase or one sub-task."""

import asyncio
from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="ResearchSubtaskWorkflow")
class ResearchSubtaskWorkflow:
    """Search, fetch and read one query. A repeat returns the stored result."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "research_subtask",
            payload,
            start_to_close_timeout=timedelta(minutes=2),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        return result if isinstance(result, dict) else {"status": "failed"}


@workflow.defn(name="ResearchWorkflow")
class ResearchWorkflow:
    """Plan, fan out, synthesise, verify. Cancel stops the next phase."""

    def __init__(self) -> None:
        self.cancelled = False

    @workflow.signal
    async def cancel(self) -> None:
        self.cancelled = True

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        step = 0
        result: dict[str, Any] = {"status": "failed", "run_id": str(payload.get("run_id") or "")}
        while step < 16 and not self.cancelled:
            result = await workflow.execute_activity(
                "research_step",
                payload,
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            if not isinstance(result, dict):
                result = {"status": "failed"}
            kind = str(result.get("kind") or "")
            if kind == "fanout":
                await self._children(payload, result.get("subtasks"))
            elif kind in {"final", "paused", "failed", "cancelled"}:
                return result
            step += 1
        if self.cancelled:
            await workflow.execute_activity(
                "research_cancel",
                payload,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            return {"status": "cancelled", "run_id": str(payload.get("run_id") or "")}
        return result

    async def _children(self, payload: dict[str, Any], raw: object) -> None:
        items = raw if isinstance(raw, list) else []
        handles = []
        for item in items:
            if not isinstance(item, dict):
                continue
            child = {
                "run_id": payload.get("run_id"),
                "id": item.get("id"),
                "text": item.get("text"),
            }
            handles.append(
                await workflow.start_child_workflow(
                    ResearchSubtaskWorkflow.run,
                    child,
                    id=f"research-{payload.get('run_id')}-{item.get('id')}",
                    cancellation_type=workflow.ChildWorkflowCancellationType.WAIT_CANCELLATION_COMPLETED,
                )
            )
        if handles:
            await asyncio.gather(*handles)

"""Section map-reduce is activities on AgentRunWorkflow, and cancel stops the next batch."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from temporalio import activity
from temporalio.worker import Worker

from ar_runtime.workflows.turn import TurnWorkflow

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment


async def test_sections_run_on_the_workflow_and_cancel_stops_the_next_batch(
    temporal_env: WorkflowEnvironment,
) -> None:
    seen: list[str] = []
    started = asyncio.Event()

    @activity.defn(name="advance_chat_step")
    async def step(payload: dict[str, Any]) -> dict[str, Any]:
        if not seen:
            return {
                "status": "running",
                "kind": "sections",
                "run_id": payload.get("run_id"),
                "sections": [
                    {"fileId": "a", "anchor": "p1-s0"},
                    {"fileId": "a", "anchor": "p1-s1"},
                    {"fileId": "a", "anchor": "p2-s0"},
                ],
            }
        return {"status": "completed", "kind": "final", "run_id": payload.get("run_id")}

    @activity.defn(name="document_section")
    async def section(payload: dict[str, Any]) -> dict[str, Any]:
        item = payload.get("section")
        anchor = str(item.get("anchor") if isinstance(item, dict) else "")
        seen.append(anchor)
        if anchor == "p1-s0":
            started.set()
            activity.heartbeat()
            await asyncio.sleep(0.3)
        return {"status": "ok", "anchor": anchor}

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": payload.get("status") or "completed", "run_id": payload.get("run_id")}

    async with Worker(
        temporal_env.client,
        task_queue="document-sections",
        workflows=[TurnWorkflow],
        activities=[step, section, finish],
    ):
        handle = await temporal_env.client.start_workflow(
            TurnWorkflow.run,
            {"run_id": "run-1", "steps": True, "document_parallelism": 1, "max_steps": 8},
            id="document-sections-1",
            task_queue="document-sections",
        )
        await asyncio.wait_for(started.wait(), 10)
        await handle.signal(TurnWorkflow.cancel)
        result = await handle.result()
    assert result["status"] == "cancelled"
    assert len(seen) < 3

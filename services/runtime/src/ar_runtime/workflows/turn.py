"""One durable chat turn. Spec: docs/03-specs/07-agent-runtime.md."""

import asyncio
from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError


@workflow.defn(name="AgentRunWorkflow")
class TurnWorkflow:
    """Keep I/O in activities and always record a terminal state."""

    def __init__(self) -> None:
        self.cancelled = False
        self.turn: workflow.ActivityHandle[dict[str, Any]] | None = None

    @workflow.signal
    async def cancel(self) -> None:
        self.cancelled = True
        if self.turn is not None:
            self.turn.cancel()

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("steps") is True:
            return await self._steps(payload)
        if not self.cancelled:
            self.turn = workflow.start_activity(
                "execute_chat_turn",
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=timedelta(seconds=10),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            try:
                result = await self.turn
                return result if isinstance(result, dict) else {"status": "completed"}
            except ActivityError, asyncio.CancelledError:
                pass
        result = await workflow.execute_activity(
            "finish_chat_turn",
            {"run_id": payload["run_id"], "status": "cancelled" if self.cancelled else "failed"},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return result if isinstance(result, dict) else {"status": "failed"}

    async def _steps(self, payload: dict[str, Any]) -> dict[str, Any]:
        """One activity is one model call or one tool call. History keeps the run id."""
        step = 0
        result: dict[str, Any] = {"status": "failed", "run_id": str(payload.get("run_id") or "")}
        while step < 32 and not self.cancelled:
            self.turn = workflow.start_activity(
                "advance_chat_step",
                {"run_id": payload.get("run_id"), "text": payload.get("text") or ""},
                start_to_close_timeout=timedelta(minutes=2),
                heartbeat_timeout=timedelta(seconds=30),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            try:
                raw = await self.turn
            except ActivityError, asyncio.CancelledError:
                break
            result = raw if isinstance(raw, dict) else result
            kind = str(result.get("kind") or "final")
            if kind not in {"model", "tools"}:
                return result
            step += 1
        if str(result.get("kind") or "") in {"model", "tools"} or self.cancelled:
            finished = await workflow.execute_activity(
                "finish_chat_turn",
                {
                    "run_id": payload["run_id"],
                    "status": "cancelled" if self.cancelled else "failed",
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            return finished if isinstance(finished, dict) else {"status": "failed"}
        return result

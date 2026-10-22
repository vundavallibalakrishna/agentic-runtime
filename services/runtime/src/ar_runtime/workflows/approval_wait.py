"""Wait for an approval or a user answer. Spec: docs/03-specs/07-agent-runtime.md §2.1."""

from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ar_runtime.activities.evaluate_control_tool import (
        evaluate_control_tool,
        record_user_input,
    )
    from ar_runtime.activities.expire_approval import cancel_approval, expire_approval


@workflow.defn
class ApprovalWaitWorkflow:
    """Pause until a signal arrives or the timer fires. A 24h wait is the default."""

    def __init__(self) -> None:
        self.decision: dict[str, Any] | None = None
        self.text: str | None = None
        self.cancelled = False

    @workflow.signal
    def approval_decided(self, payload: dict[str, Any]) -> None:
        """Signal ``approval_decided`` from the approvals service."""
        self.decision = payload

    @workflow.signal
    def user_input(self, payload: dict[str, Any]) -> None:
        """Signal ``user_input`` from ``POST /runs/{id}:input``."""
        self.text = str(payload.get("text") or "")

    @workflow.signal
    def cancel_wait(self) -> None:
        """Cancel the wait and the pending approval."""
        self.cancelled = True

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        wait_s = _count(payload.get("wait_s"), 86400)
        kind = str(payload.get("kind") or "approval")
        approval_id = str(payload.get("approval_id") or "")
        run_id = str(payload.get("run_id") or "")
        limit = timedelta(seconds=wait_s)
        if kind == "input":
            return await self._input(run_id, limit)
        return await self._approval(approval_id, run_id, limit)

    async def _input(self, run_id: str, limit: timedelta) -> dict[str, Any]:
        try:
            await workflow.wait_condition(
                lambda: self.text is not None or self.cancelled, timeout=limit
            )
        except TimeoutError:
            return {"status": "expired", "run_id": run_id}
        if self.cancelled:
            return {"status": "cancelled", "run_id": run_id}
        recorded = await workflow.execute_activity(
            record_user_input,
            {"run_id": run_id, "text": self.text or ""},
            start_to_close_timeout=timedelta(seconds=30),
        )
        length = recorded.get("length") if isinstance(recorded, dict) else 0
        return {"status": "completed", "length": length, "run_id": run_id}

    async def _approval(self, approval_id: str, run_id: str, limit: timedelta) -> dict[str, Any]:
        try:
            await workflow.wait_condition(
                lambda: self.decision is not None or self.cancelled, timeout=limit
            )
        except TimeoutError:
            expired = await workflow.execute_activity(
                expire_approval, approval_id, start_to_close_timeout=timedelta(seconds=30)
            )
            return {"status": "expired", "activity": expired, "run_id": run_id}
        if self.cancelled:
            cancelled = await workflow.execute_activity(
                cancel_approval, approval_id, start_to_close_timeout=timedelta(seconds=30)
            )
            return {"status": "cancelled", "activity": cancelled, "run_id": run_id}
        decision = self.decision or {}
        if str(decision.get("status") or "") == "rejected":
            return {
                "status": "rejected",
                "reason": str(decision.get("reason") or ""),
                "run_id": run_id,
            }
        executed = await workflow.execute_activity(
            evaluate_control_tool,
            {"approval_id": approval_id, "run_id": run_id},
            start_to_close_timeout=timedelta(seconds=30),
        )
        return {"status": "completed", "activity": executed, "run_id": run_id}


def _count(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default

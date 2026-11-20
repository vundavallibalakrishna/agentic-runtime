"""One durable chat turn. Spec: docs/03-specs/07-agent-runtime.md.

``AgentRunWorkflow`` is the only run path. One activity is one model call, one
tool call, or one research phase. A pause for approval or input waits on a
signal. A long run continues as new so history stays bounded; the step cap is
the payload's ``max_steps`` (the run budget), and ``history_steps`` is how many
activities this execution records before continuing. One step activity may take
the payload's ``step_timeout_s``, which the starter derives from the run's wall
clock; a worker that dies is noticed sooner, by the heartbeat.
"""

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
        self.sections: list[workflow.ActivityHandle[dict[str, Any]]] = []
        self.decision: dict[str, Any] | None = None
        self.answer: str | None = None

    @workflow.signal
    async def cancel(self) -> None:
        self.cancelled = True
        if self.turn is not None:
            self.turn.cancel()
        for handle in getattr(self, "sections", ()):
            handle.cancel()

    @workflow.signal
    async def approval_decided(self, payload: dict[str, Any]) -> None:
        """An approval decision. The next activity runs or stops the tool call."""
        self.decision = payload if isinstance(payload, dict) else {"status": "approved"}

    @workflow.signal
    async def user_input(self, payload: Any) -> None:
        """A person's answer for a run that asked a question."""
        if isinstance(payload, dict):
            self.answer = str(payload.get("text") or "")
        else:
            self.answer = str(payload)

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

    async def _steps(self, payload: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
        """Step until the budget, a pause, or this execution's history cap."""
        max_steps = _count(payload.get("max_steps"), 8)
        history_steps = _count(payload.get("history_steps"), 24)
        taken = _count(payload.get("steps_taken"), 0)
        step_timeout = timedelta(seconds=_count(payload.get("step_timeout_s"), 120))
        step = 0
        carried = payload.get("decision")
        decision = carried if isinstance(carried, dict) else None
        result: dict[str, Any] = {"status": "failed", "kind": "final", "run_id": _run_id(payload)}
        while taken < max_steps and step < history_steps and not self.cancelled:
            if step > 0 and workflow.info().is_continue_as_new_suggested():
                break
            body: dict[str, Any] = {
                "run_id": payload.get("run_id"),
                "text": payload.get("text") or "",
            }
            if decision is not None:
                body["decision"] = decision
                decision = None
            self.turn = workflow.start_activity(
                "advance_chat_step",
                body,
                start_to_close_timeout=step_timeout,
                heartbeat_timeout=timedelta(seconds=30),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            try:
                raw = await self.turn
            except ActivityError, asyncio.CancelledError:
                break
            self.turn = None
            result = raw if isinstance(raw, dict) else result
            kind = str(result.get("kind") or "final")
            status = str(result.get("status") or "")
            taken += 1
            step += 1
            if self.cancelled:
                break
            if kind == "fanout":
                await self._fanout(payload, result.get("subtasks"))
                continue
            if kind == "sections":
                await self._sections(payload, result.get("sections"))
                continue
            if kind == "paused" or status in {"waiting_approval", "waiting_input"}:
                decision = await self._await_person(payload, result)
                if decision is None:
                    break
                continue
            if kind not in {"model", "tools"}:
                return result
        kind = str(result.get("kind") or "")
        if (
            not self.cancelled
            and taken < max_steps
            and kind in {"model", "tools", "fanout", "paused", "sections"}
        ):
            await workflow.wait_condition(workflow.all_handlers_finished)
            continued = {
                key: value
                for key, value in payload.items()
                if key not in {"decision", "steps_taken"}
            }
            continued.update(
                steps=True,
                max_steps=max_steps,
                history_steps=history_steps,
                step_timeout_s=int(step_timeout.total_seconds()),
                steps_taken=taken,
            )
            if decision is not None:
                continued["decision"] = decision
            workflow.continue_as_new(continued)
        if kind in {"model", "tools", "fanout", "paused", "sections"} or self.cancelled:
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

    async def _await_person(
        self, payload: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Wait for a signal. None means the run was cancelled while waiting.

        A signal that arrived before the wait is kept. Only the signal this wait
        consumed is cleared, so an input that landed during an approval wait is
        still there for the next pause.
        """
        wait_s = _count(payload.get("wait_s"), 86400)
        status = str(result.get("status") or "")
        limit = timedelta(seconds=wait_s)
        try:
            if status == "waiting_input":
                await workflow.wait_condition(
                    lambda: self.answer is not None or self.cancelled, timeout=limit
                )
            else:
                await workflow.wait_condition(
                    lambda: self.decision is not None or self.cancelled, timeout=limit
                )
        except TimeoutError:
            return {
                "status": "expired",
                "approval_id": str(result.get("approval_id") or ""),
            }
        if self.cancelled:
            return None
        if status == "waiting_input":
            text = self.answer or ""
            self.answer = None
            return {"status": "input", "text": text}
        found = dict(self.decision or {"status": "approved"})
        self.decision = None
        return found

    async def _fanout(self, payload: dict[str, Any], raw: object) -> None:
        """Run research sub-tasks as activities of this workflow, then the next step collects."""
        items = raw if isinstance(raw, list) else []
        handles = []
        for item in items:
            if not isinstance(item, dict):
                continue
            handles.append(
                workflow.start_activity(
                    "research_subtask",
                    {
                        "run_id": payload.get("run_id"),
                        "id": item.get("id"),
                        "text": item.get("text"),
                    },
                    start_to_close_timeout=timedelta(minutes=2),
                    heartbeat_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            )
        if handles:
            await asyncio.gather(*handles)

    async def _sections(self, payload: dict[str, Any], raw: object) -> None:
        """Read document sections a few at a time. Cancelling stops the next batch."""
        items = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        width = _count(payload.get("document_parallelism"), 2)
        pending = list(items)
        while pending and not self.cancelled:
            batch = pending[:width]
            pending = pending[width:]
            self.sections = [
                workflow.start_activity(
                    "document_section",
                    {"run_id": payload.get("run_id"), "section": item},
                    start_to_close_timeout=timedelta(minutes=5),
                    heartbeat_timeout=timedelta(seconds=30),
                    cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
                for item in batch
            ]
            if self.sections:
                try:
                    await asyncio.gather(*self.sections)
                except ActivityError:
                    if self.cancelled:
                        self.sections = []
                        return
                    raise
            self.sections = []


def _count(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return default
    return value


def _run_id(payload: dict[str, Any]) -> str:
    return str(payload.get("run_id") or "")

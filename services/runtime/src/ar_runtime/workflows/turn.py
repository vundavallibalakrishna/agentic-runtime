"""One durable chat turn. Spec: docs/03-specs/07-agent-runtime.md.

``AgentRunWorkflow`` is the only run path. One activity is one model call, one
tool call, or one research phase. A pause for approval or input waits on a
signal. A call to other agents starts one child workflow of this same type for each and
waits for them: a called agent is a run like any other, with its own id, its own pauses
and its own history. A long run continues as new so history stays bounded; the step cap is
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
        self.called: list[workflow.ChildWorkflowHandle[Any, Any]] = []
        self.decision: dict[str, Any] | None = None
        self.answer: str | None = None

    @workflow.signal
    async def cancel(self) -> None:
        self.cancelled = True
        if self.turn is not None:
            self.turn.cancel()
        for handle in getattr(self, "sections", ()):
            handle.cancel()
        # Stopping an agent stops the agents it called. Each closes its own run.
        for child in list(getattr(self, "called", ())):
            await child.signal("cancel")

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
            {
                "run_id": payload["run_id"],
                "status": "cancelled" if self.cancelled else "failed",
                "reason": "step_failed",
            },
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
        # Why the run is ended here when it did not end itself: recorded on the run.
        why = ""
        # What the last fan-out's sub-tasks returned. The next step stores all of it, so a
        # result one parallel sub-task overwrote on another is put back.
        found: dict[str, Any] = {}
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
            if found:
                body["results"] = found
                found = {}
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
                why = "step_failed"
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
                found = await self._fanout(payload, result.get("subtasks"))
                continue
            if kind == "sections":
                await self._sections(payload, result.get("sections"))
                continue
            if kind == "agents":
                await self._agents(result.get("children"))
                continue
            if kind == "paused" or status in {"waiting_approval", "waiting_input"}:
                decision = await self._await_person(payload, result)
                if decision is None:
                    why = "wait_ended"
                    break
                continue
            if kind not in {"model", "tools"}:
                return result
        kind = str(result.get("kind") or "")
        if (
            not self.cancelled
            and taken < max_steps
            and kind in {"model", "tools", "fanout", "paused", "sections", "agents"}
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
        if kind in {"model", "tools", "fanout", "paused", "sections", "agents"} or self.cancelled:
            if not why:
                why = "step_limit" if taken >= max_steps else "step_failed"
            finished = await workflow.execute_activity(
                "finish_chat_turn",
                {
                    "run_id": payload["run_id"],
                    "status": "cancelled" if self.cancelled else "failed",
                    "reason": why,
                    "steps": taken,
                    "max_steps": max_steps,
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

    async def _fanout(self, payload: dict[str, Any], raw: object) -> dict[str, Any]:
        """Run research sub-tasks as activities of this workflow and return what each found.

        The sub-tasks run side by side and each saves the run. The last save wins, so the
        next step is handed every result and stores them together.
        """
        items = raw if isinstance(raw, list) else []
        handles = []
        ids: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            ids.append(str(item.get("id") or ""))
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
        if not handles:
            return {}
        results = await asyncio.gather(*handles)
        return {
            key: value for key, value in zip(ids, results, strict=True) if isinstance(value, dict)
        }

    async def _agents(self, raw: object) -> None:
        """Run each called agent as a child workflow and wait until all have ended.

        What a child returns is not used: the caller's next step reads how each run
        ended from the database, and closes one that did not end. A child that could
        not be started, or whose workflow failed, is left for that step in the same way.
        """
        items = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        for item in items:
            if self.cancelled:
                break
            try:
                handle = await workflow.start_child_workflow(
                    "AgentRunWorkflow",
                    item,
                    id=f"run-{item.get('run_id')}",
                    parent_close_policy=workflow.ParentClosePolicy.REQUEST_CANCEL,
                )
            except Exception:  # noqa: BLE001, S112 - the next step closes a run that never started
                continue
            self.called.append(handle)
        if self.cancelled:
            for child in self.called:
                await child.signal("cancel")
        await asyncio.gather(*self.called, return_exceptions=True)
        self.called = []

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

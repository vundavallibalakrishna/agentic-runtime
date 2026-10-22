"""Tool-call turn. Spec: docs/03-specs/07-agent-runtime.md §2.

The dev API still runs tools in process. This driver is what the worker executes,
including a Temporal workflow that calls the same steps.
"""

from dataclasses import dataclass, field

from temporalio import workflow

_NON_RETRYABLE = frozenset({"validation_failed", "policy_denied", "not_entitled", "tool_disabled"})


def _count(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default


def _optional_count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


@dataclass
class PlannedCall:
    name: str
    fail_code: str = ""
    attempts_until_success: int = 1


@dataclass
class TurnResult:
    status: str
    events: list[dict[str, object]] = field(default_factory=list)
    calls: int = 0


def drive_tool_turn(
    calls: list[PlannedCall],
    *,
    parallel: int,
    error_limit: int,
    max_calls: int,
    cancel_after: int | None = None,
) -> TurnResult:
    """Run a scripted turn. Validation and policy errors are not retried."""
    events: list[dict[str, object]] = []
    consecutive = 0
    completed = 0
    width = max(1, parallel)
    index = 0
    while index < len(calls) and completed < max_calls:
        if cancel_after is not None and completed >= cancel_after:
            events.append({"type": "run.cancelled"})
            return TurnResult("cancelled", events, completed)
        batch = calls[index : index + width]
        index += len(batch)
        for call in batch:
            if completed >= max_calls:
                break
            outcome = _one(call)
            completed += 1
            events.append({"type": "tool_call.started", "name": call.name})
            events.append({"type": outcome["event"], "name": call.name, "code": outcome["code"]})
            if outcome["ok"]:
                consecutive = 0
            else:
                consecutive += 1
                if consecutive >= error_limit:
                    events.append({"type": "run.failed", "code": "consecutive_tool_errors"})
                    return TurnResult("failed", events, completed)
    events.append({"type": "run.completed"})
    return TurnResult("completed", events, completed)


def run_planned(call: PlannedCall) -> dict[str, object]:
    """One call, with at most three attempts for retryable failures."""
    return _one(call)


def _one(call: PlannedCall) -> dict[str, object]:
    if call.fail_code in _NON_RETRYABLE:
        return {"ok": False, "event": "tool_call.failed", "code": call.fail_code, "attempts": 1}
    attempts = 0
    while attempts < 3:
        attempts += 1
        if attempts >= call.attempts_until_success and not call.fail_code:
            return {"ok": True, "event": "tool_call.completed", "code": "", "attempts": attempts}
        if call.fail_code and attempts >= 3:
            return {
                "ok": False,
                "event": "tool_call.failed",
                "code": call.fail_code,
                "attempts": attempts,
            }
    return {
        "ok": False,
        "event": "tool_call.failed",
        "code": call.fail_code or "upstream_error",
        "attempts": attempts,
    }


@workflow.defn
class ToolTurnWorkflow:
    """Temporal shell. Activities receive the same planned calls the driver uses."""

    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        raw = payload.get("calls")
        calls = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    calls.append(  # noqa: PERF401
                        PlannedCall(
                            name=str(item.get("name") or "tool"),
                            fail_code=str(item.get("fail_code") or ""),
                            attempts_until_success=_count(item.get("attempts_until_success"), 1),
                        )
                    )
        result = drive_tool_turn(
            calls,
            parallel=_count(payload.get("parallel"), 1),
            error_limit=_count(payload.get("error_limit"), 3),
            max_calls=_count(payload.get("max_calls"), 8),
            cancel_after=_optional_count(payload.get("cancel_after")),
        )
        return {"status": result.status, "events": result.events, "calls": result.calls}

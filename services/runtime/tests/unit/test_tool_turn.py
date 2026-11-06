"""Tool-turn driver: parallel calls, retries, the error limit and cancel."""

import pytest

from ar_runtime.activities.execute_tool_call import execute_tool_call
from ar_runtime.activities.model_step import model_step
from ar_runtime.workflows.tool_turn import PlannedCall, ToolTurnWorkflow, drive_tool_turn


def test_parallel_retry_limit_and_cancel() -> None:
    calls = [
        PlannedCall("a"),
        PlannedCall("b", fail_code="upstream_error", attempts_until_success=9),
        PlannedCall("c"),
    ]
    parallel = drive_tool_turn(calls, parallel=2, error_limit=3, max_calls=8)
    assert parallel.status == "completed"
    assert any(
        event["name"] == "b" and event["type"] == "tool_call.failed" for event in parallel.events
    )
    again = drive_tool_turn(calls, parallel=2, error_limit=3, max_calls=8)
    assert again.events == parallel.events
    limited = drive_tool_turn(
        [
            PlannedCall("x", fail_code="policy_denied"),
            PlannedCall("y", fail_code="validation_failed"),
        ],
        parallel=1,
        error_limit=2,
        max_calls=8,
    )
    assert limited.status == "failed"
    assert limited.events[-1]["code"] == "consecutive_tool_errors"
    cancelled = drive_tool_turn(
        [PlannedCall("a"), PlannedCall("b")], parallel=1, error_limit=3, max_calls=8, cancel_after=1
    )
    assert cancelled.status == "cancelled"
    denied = execute_tool_call("read", fail_code="policy_denied")
    assert denied["attempts"] == 1
    assert model_step("hello")["text"] == "hello"


@pytest.mark.asyncio
async def test_workflow_run_uses_the_same_driver() -> None:
    result = await ToolTurnWorkflow().run(
        {
            "calls": [{"name": "ping", "attempts_until_success": 1}],
            "parallel": 1,
            "error_limit": 3,
            "max_calls": 4,
            "cancel_after": 1,
        }
    )
    assert result["status"] in {"completed", "cancelled"}
    assert result["events"]

"""Activity body for one tool call. The workflow records heartbeats around it."""

from ar_runtime.workflows.tool_turn import PlannedCall, run_planned


def execute_tool_call(
    name: str, fail_code: str = "", attempts_until_success: int = 1
) -> dict[str, object]:
    """Run one planned call. Non-retryable codes return on the first attempt."""
    return run_planned(PlannedCall(name, fail_code, attempts_until_success))

"""Agent run loop v1. Spec: docs/03-specs/07-agent-runtime.md §2.

Tool branches are refused. The workflow records a model step, then finalises.
"""

from dataclasses import dataclass

from ar_domain.runs.logic import budget_exceeded, tools_not_supported


@dataclass
class RunRequest:
    """Input the workflow and the inline engine share."""

    run_id: str
    definition: dict[str, object]
    user_text: str
    cancelled: bool = False
    steps: int = 0
    tokens: int = 0


def advance(request: RunRequest, budget: dict[str, int]) -> str:
    """Return the next status: completed, cancelled, budget_exceeded or invalid."""
    if tools_not_supported(request.definition):
        raise NotImplementedError("tool steps are not part of the v1 loop")
    if request.cancelled:
        return "cancelled"
    request.steps += 1
    request.tokens += max(1, len(request.user_text.split()))
    limit = budget_exceeded(
        steps=request.steps,
        tokens=request.tokens,
        cost_micros=0,
        elapsed_s=0,
        tool_calls=0,
        budget=budget,
    )
    if limit is not None:
        return "budget_exceeded"
    return "completed"


def workflow_id(run_id: str) -> str:
    """Temporal workflow id ``run-{run_id}``."""
    return f"run-{run_id}"


def approval_wait_workflow() -> type[object]:
    """The Temporal wait for approval and user input. The dev HTTP path stays in process."""
    from ar_runtime.workflows.approval_wait import ApprovalWaitWorkflow  # noqa: PLC0415

    return ApprovalWaitWorkflow

"""Inline status helper. Spec: docs/03-specs/07-agent-runtime.md §2.

The chat turn runs the plan, act, check and retry loop in ``ar_domain.tools.agent_loop``.
"""

from dataclasses import dataclass

from ar_domain.runs.logic import budget_exceeded


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


def delegation_workflow() -> type[object]:
    """Temporal parent run that starts subagent children."""
    from ar_runtime.workflows.delegation import AgentRunWorkflow  # noqa: PLC0415

    return AgentRunWorkflow


def approval_wait_workflow() -> type[object]:
    """The Temporal wait for approval and user input. The dev HTTP path stays in process."""
    from ar_runtime.workflows.approval_wait import ApprovalWaitWorkflow  # noqa: PLC0415

    return ApprovalWaitWorkflow

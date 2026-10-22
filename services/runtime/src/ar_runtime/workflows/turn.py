"""One chat turn. Spec: docs/03-specs/07-agent-runtime.md.

The Temporal name is ``AgentRunWorkflow`` so routines can start the child the
spec names. The delegation parent is registered as ``DelegationWorkflow``.
"""

from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="AgentRunWorkflow")
class TurnWorkflow:
    """Generate one answer. The activity owns the model call."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await workflow.execute_activity(
            "execute_chat_turn",
            payload,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return result if isinstance(result, dict) else {"status": "completed"}

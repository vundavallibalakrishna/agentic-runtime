"""EvalRunWorkflow. Spec: docs/03-specs/18-observability-eval.md §4.2."""

from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import uuid

    from ar_domain.evals.runner import execute_eval_run
    from ar_system.routines_store import current_store

EVAL_QUEUE = "ar-eval"


@activity.defn(name="execute_eval_run")
async def execute_eval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = current_store()
    summary = execute_eval_run(store, uuid.UUID(str(payload["eval_run_id"])))
    return {str(key): value for key, value in summary.items()}


@workflow.defn(name="EvalRunWorkflow")
class EvalRunWorkflow:
    """Score a suite. The id is ``eval-{eval_run_id}`` on queue ``ar-eval``."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            execute_eval_activity,
            payload,
            start_to_close_timeout=timedelta(minutes=10),
        )

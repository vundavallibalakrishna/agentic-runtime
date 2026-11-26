"""EvalRunWorkflow. Spec: docs/03-specs/18-observability-eval.md §4.2."""

import asyncio
from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    import uuid

    from ar_domain.evals.runner import (
        begin_eval_run,
        eval_concurrency,
        execute_eval_run,
        fail_eval_run,
        finish_eval_run,
        score_eval_case,
    )
    from ar_domain.readmodel.activity import repository_activity
    from ar_system.routines_store import current_store, process_store

EVAL_QUEUE = "ar-eval"
# One case posts each user turn and waits for every run it starts, then the judge.
_CASE_LIMIT = timedelta(minutes=15)
_STEP_LIMIT = timedelta(minutes=2)
_PER_CASE = "eval-run-per-case"


@activity.defn(name="execute_eval_run")
@repository_activity(process_store)
async def execute_eval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """The whole run in one activity. Kept for runs started before per-case activities."""
    store = current_store()
    summary = await execute_eval_run(store, uuid.UUID(str(payload["eval_run_id"])))
    return {str(key): value for key, value in summary.items()}


@activity.defn(name="begin_eval_run")
@repository_activity(process_store)
async def begin_eval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = current_store()
    cases = begin_eval_run(store, uuid.UUID(str(payload["eval_run_id"])))
    return {"case_ids": cases, "concurrency": eval_concurrency()}


@activity.defn(name="score_eval_case")
@repository_activity(process_store)
async def score_eval_case_activity(payload: dict[str, Any]) -> bool:
    store = current_store()
    return await score_eval_case(
        store, uuid.UUID(str(payload["eval_run_id"])), str(payload["case_id"])
    )


@activity.defn(name="finish_eval_run")
@repository_activity(process_store)
async def finish_eval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = current_store()
    summary = finish_eval_run(store, uuid.UUID(str(payload["eval_run_id"])))
    return {str(key): value for key, value in summary.items()}


@activity.defn(name="fail_eval_run")
@repository_activity(process_store)
async def fail_eval_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = current_store()
    summary = fail_eval_run(store, uuid.UUID(str(payload["eval_run_id"])), str(payload["reason"]))
    return {str(key): value for key, value in summary.items()}


EVAL_ACTIVITIES = [
    execute_eval_activity,
    begin_eval_activity,
    score_eval_case_activity,
    finish_eval_activity,
    fail_eval_activity,
]


@workflow.defn(name="EvalRunWorkflow")
class EvalRunWorkflow:
    """Score a suite. The id is ``eval-{eval_run_id}`` on queue ``ar-eval``.

    Each case is its own activity, several at a time, so a suite of any size finishes
    and a case that times out is saved as failed instead of ending the run.
    """

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not workflow.patched(_PER_CASE):
            return await workflow.execute_activity(
                execute_eval_activity, payload, start_to_close_timeout=timedelta(minutes=10)
            )
        try:
            begun = await workflow.execute_activity(
                begin_eval_activity, payload, start_to_close_timeout=_STEP_LIMIT
            )
            gate_keeper = asyncio.Semaphore(max(1, int(begun.get("concurrency") or 1)))

            async def one(case_id: str) -> None:
                async with gate_keeper:
                    try:
                        await workflow.execute_activity(
                            score_eval_case_activity,
                            {**payload, "case_id": case_id},
                            start_to_close_timeout=_CASE_LIMIT,
                            retry_policy=RetryPolicy(maximum_attempts=2),
                        )
                    except ActivityError:
                        # The finish step saves a case with no result as failed.
                        return

            await asyncio.gather(*(one(str(case_id)) for case_id in begun.get("case_ids") or []))
            return await workflow.execute_activity(
                finish_eval_activity, payload, start_to_close_timeout=_STEP_LIMIT
            )
        except ActivityError as exc:
            return await workflow.execute_activity(
                fail_eval_activity,
                {**payload, "reason": type(exc.cause or exc).__name__},
                start_to_close_timeout=_STEP_LIMIT,
            )

"""EvalRunWorkflow on the time-skipping server."""

import uuid

import pytest
from temporalio import activity
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
    Worker,
)

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_system.routines_store import bind_store
from ar_system.workflows.eval_run import EVAL_ACTIVITIES, EVAL_QUEUE, EvalRunWorkflow
from ar_testing.demo import connect_chat, demo_store

pytestmark = pytest.mark.asyncio


async def test_workflow_scores_a_suite(temporal_env) -> None:  # type: ignore[no-untyped-def]
    store = demo_store()
    connect_chat(store, demo_id("tenant"))
    bind_store(store)
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
    )
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Workflow", "kind": "functional"})
    for name in ("hello", "hello again", "hello once more"):
        book.create_case(
            actor,
            suite["id"],  # type: ignore[arg-type]
            {
                "name": name,
                "input": {"messages": ["Say hello"]},
                "assertions": [{"type": "contains", "value": "Say hello"}],
            },
        )

    store.defer_eval_runs = True
    queued = book.start_run(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {"agent_version_ref": "published"},
    )
    assert queued["status"] == "queued"
    async with Worker(
        temporal_env.client,
        task_queue=EVAL_QUEUE,
        workflows=[EvalRunWorkflow],
        activities=EVAL_ACTIVITIES,
    ):
        summary = await temporal_env.client.execute_workflow(
            EvalRunWorkflow.run,
            {"eval_run_id": str(queued["id"])},
            id=f"eval-{queued['id']}",
            task_queue=EVAL_QUEUE,
        )
    assert summary["pass_rate"] == 1
    assert summary["cases"] == 3
    run_id = uuid.UUID(str(queued["id"]))
    assert store.eval_runs[run_id]["status"] == "completed"
    # Each case was scored in its own activity and saved once.
    saved = [row for row in store.eval_results.values() if row["eval_run_id"] == run_id]
    assert len(saved) == 3


async def test_cases_are_scored_in_batches_one_activity_each(  # type: ignore[no-untyped-def]
    temporal_env, monkeypatch
) -> None:
    from ar_system.workflows import eval_run

    store = demo_store()
    connect_chat(store, demo_id("tenant"))
    bind_store(store)
    actor = Actor(
        tenant_id=demo_id("tenant"), user_id=demo_id("admin"), permissions=PERMISSION_KEYS
    )
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Batches", "kind": "functional"})
    for index in range(5):
        book.create_case(
            actor,
            suite["id"],  # type: ignore[arg-type]
            {
                "name": f"hello {index}",
                "input": {"messages": ["Say hello"]},
                "assertions": [{"type": "contains", "value": "Say hello"}],
            },
        )
    monkeypatch.setattr(eval_run, "eval_concurrency", lambda: 2)
    batches: list[int] = []
    store.defer_eval_runs = True
    queued = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    async with Worker(
        temporal_env.client,
        task_queue=EVAL_QUEUE,
        workflows=[EvalRunWorkflow],
        activities=EVAL_ACTIVITIES,
        interceptors=[_CountBatches(batches)],
    ):
        summary = await temporal_env.client.execute_workflow(
            EvalRunWorkflow.run,
            {"eval_run_id": str(queued["id"])},
            id=f"eval-{queued['id']}",
            task_queue=EVAL_QUEUE,
        )
    assert summary["cases"] == 5
    assert summary["pass_rate"] == 1
    # Five cases two at a time: three batch activities, one load of the tenant each.
    assert batches == [2, 2, 1]


class _CountBatches(Interceptor):
    def __init__(self, sizes: list[int]) -> None:
        self.sizes = sizes

    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:  # noqa: A002
        sizes = self.sizes

        class _Inbound(ActivityInboundInterceptor):
            async def execute_activity(self, input: ExecuteActivityInput) -> object:  # noqa: A002
                if activity.info().activity_type == "score_eval_cases":
                    sizes.append(len(input.args[0]["case_ids"]))
                return await super().execute_activity(input)

        return _Inbound(next)

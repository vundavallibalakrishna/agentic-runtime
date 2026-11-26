"""EvalRunWorkflow on the time-skipping server."""

import uuid

import pytest
from temporalio.worker import Worker

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

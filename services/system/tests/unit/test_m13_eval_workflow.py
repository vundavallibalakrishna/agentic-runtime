"""EvalRunWorkflow on the time-skipping server."""

import uuid

import pytest
from temporalio.worker import Worker

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_system.routines_store import bind_store
from ar_system.workflows.eval_run import EVAL_QUEUE, EvalRunWorkflow, execute_eval_activity

pytestmark = pytest.mark.asyncio


async def test_workflow_scores_a_suite(temporal_env) -> None:  # type: ignore[no-untyped-def]
    store = ChatService()
    bind_store(store)
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
    )
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Workflow", "kind": "functional"})
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "hello",
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "Say hello"}],
        },
    )

    class _Client:
        def start_workflow(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

    store.temporal_client = _Client()
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
        activities=[execute_eval_activity],
    ):
        summary = await temporal_env.client.execute_workflow(
            EvalRunWorkflow.run,
            {"eval_run_id": str(queued["id"])},
            id=f"eval-{queued['id']}",
            task_queue=EVAL_QUEUE,
        )
    assert summary["pass_rate"] == 1
    assert store.eval_runs[uuid.UUID(str(queued["id"]))]["status"] == "completed"

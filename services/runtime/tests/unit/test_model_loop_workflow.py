"""A bad tool call is handed back on AgentRunWorkflow, which is the only run path."""

import uuid
from typing import TYPE_CHECKING

import pytest
from temporalio import activity
from temporalio.worker import Worker

from ar_domain.demo_ids import demo_id
from ar_runtime.activities.advance_chat_step import advance_chat_step
from ar_runtime.activities.expire_approval import bind_store
from ar_runtime.workflows.turn import TurnWorkflow
from ar_testing.demo import demo_store
from ar_testing.retry_tool import MODEL_NAME, offer_retry_tool

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment


@pytest.mark.asyncio
async def test_malformed_tool_arguments_retry_on_the_workflow(
    temporal_env: WorkflowEnvironment,
) -> None:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)  # type: ignore[method-assign]
    steps = [
        {
            "text": "",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": MODEL_NAME,
                    "arguments": {},
                    "arguments_error": "tool arguments were not valid JSON",
                }
            ],
            "usage": {"tokens_in": 2, "tokens_out": 1, "usage_source": "provider"},
            "real": True,
        },
        {
            "text": "saved nothing",
            "tool_calls": [],
            "usage": {"tokens_in": 3, "tokens_out": 2, "usage_source": "provider"},
            "real": True,
        },
    ]

    async def complete(*_args: object, **_kwargs: object) -> dict[str, object]:
        return steps.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant = demo_id("tenant")
    user = demo_id("admin")
    offer_retry_tool(store, tenant)
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Save a note", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))

    @activity.defn(name="finish_chat_turn")
    async def finish(payload: dict[str, str]) -> dict[str, str]:
        return payload

    bind_store(store)
    queue = f"model-loop-{uuid.uuid4()}"
    try:
        async with Worker(
            temporal_env.client,
            task_queue=queue,
            workflows=[TurnWorkflow],
            activities=[advance_chat_step, finish],
        ):
            result = await temporal_env.client.execute_workflow(
                TurnWorkflow.run,
                {"run_id": str(run_id), "steps": True, "text": "Save a note"},
                id=queue,
                task_queue=queue,
            )
    finally:
        bind_store(None)
    assert result["status"] == "completed"
    run = store.runs[run_id]
    answer = str(store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"])
    assert "saved nothing" in answer
    previews = store.messages[uuid.UUID(str(run["assistant_message_id"]))]["tool_calls"]
    assert isinstance(previews, list) and previews
    assert "not valid JSON" in str(previews[0])

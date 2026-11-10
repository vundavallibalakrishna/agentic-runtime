"""The summary activity stores a fold. Two replicas are the contract test."""

from __future__ import annotations

import uuid

from temporalio.worker import Worker

from ar_domain.chat.service import demo_id
from ar_domain.conversations.summary import read_summary
from ar_system.routines_store import bind_store
from ar_system.workflows.summary_refresh import (
    ConversationSummaryWorkflow,
    refresh_conversation_summary,
)
from ar_testing.demo import demo_store


def _store() -> tuple[object, uuid.UUID, uuid.UUID]:
    store = demo_store()
    tenant = demo_id("tenant")
    conversation_id = uuid.uuid4()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": tenant,
        "rolling_summary": "",
    }
    for index in range(6):
        message_id = uuid.uuid4()
        store.messages[message_id] = {
            "id": message_id,
            "tenant_id": tenant,
            "conversation_id": conversation_id,
            "created_at": f"2026-01-0{index + 1}T00:00:00Z",
            "role": "user",
            "content": "The team agreed to keep the weekly note.",
            "text": "The team agreed to keep the weekly note.",
        }
    bind_store(store)
    return store, tenant, conversation_id


async def test_summary_workflow_stores_the_fold(temporal_env: object) -> None:
    store, tenant, conversation_id = _store()
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="ar-system-summary",
        workflows=[ConversationSummaryWorkflow],
        activities=[refresh_conversation_summary],
    ):
        result = await client.execute_workflow(
            ConversationSummaryWorkflow.run,
            {"tenant_id": str(tenant), "conversation_id": str(conversation_id)},
            id="stage12-summary",
            task_queue="ar-system-summary",
        )
    assert result["summary"]
    assert read_summary(store, tenant, conversation_id)["summary"] == result["summary"]

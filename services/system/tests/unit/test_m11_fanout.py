"""Notification fan-out delivers a Slack DM through the channel catalogue."""

import uuid

import pytest
from temporalio.worker import Worker

from ar_domain.chat.service import ChatService, demo_id
from ar_system.routines_store import bind_store
from ar_system.workflows.notification_fanout import (
    NotificationFanoutWorkflow,
    deliver_activity,
    notices_for,
    resolve_activity,
)

pytestmark = pytest.mark.asyncio


async def test_fanout_posts_to_slack(temporal_env: object) -> None:
    store = ChatService()
    store.seed_demo()
    store.seed_showcase()
    bind_store(store)
    client = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        client,
        task_queue="ar-system",
        workflows=[NotificationFanoutWorkflow],
        activities=[resolve_activity, deliver_activity],
    ):
        result = await client.execute_workflow(
            NotificationFanoutWorkflow.run,
            {
                "topic": "approval.requested",
                "user_id": str(demo_id("admin")),
                "payload": {"qualified_name": "delivery.slack_post"},
            },
            id=f"notify-{uuid.uuid4()}",
            task_queue="ar-system",
        )
    assert "slack" in result["delivered"]
    assert any(row.get("kind") == "slack" for row in store.channel_posts.values())
    assert notices_for("approval.requested", {})[0].kind == "approval_requested"

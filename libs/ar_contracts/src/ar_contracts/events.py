"""Outbox envelope and known topics. Spec: docs/05-contracts/domain-events.md."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from ar_contracts.json_api import ApiModel


class _Model(ApiModel):
    """Event envelope. Keys on the wire are camelCase."""


class DomainEvent(_Model):
    """Envelope written to ``outbox_events.payload`` is the inner payload.

    The row stores ``topic`` and ``payload`` separately. This model is the
    validated payload plus the envelope fields callers pass to ``emit``.
    """

    id: uuid.UUID
    topic: str
    tenant_id: uuid.UUID | None
    occurred_at: datetime
    version: int = 1
    payload: dict[str, JsonValue] = Field(default_factory=dict)


PUBLIC_TOPICS: frozenset[str] = frozenset(
    {
        "user.provisioned",
        "user.deprovisioned",
        "agent.published",
        "agent.disabled",
        "agent.enabled",
        "tool.disabled",
        "tool.enabled",
        "run.started",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.budget_exceeded",
        "feedback.created",
        "approval.requested",
        "approval.decided",
        "routine.run_completed",
        "routine.paused",
        "knowledge.ingestion_completed",
        "file.ready",
        "quota.warning",
        "quota.exceeded",
        "audit.event",
        "eval.completed",
    }
)

TopicName = Literal[
    "tenant.created",
    "tenant.suspended",
    "user.provisioned",
    "user.deprovisioned",
    "invitation.created",
    "agent.published",
    "agent.disabled",
    "agent.enabled",
    "tool_server.review_requested",
    "tool_server.review_decided",
    "tool.disabled",
    "tool.enabled",
    "model_alias.updated",
    "policy.activated",
    "policy.disabled",
    "skill.published",
    "run.start_requested",
    "run.started",
    "run.completed",
    "run.failed",
    "run.cancelled",
    "run.budget_exceeded",
    "conversation.shared",
    "feedback.created",
    "approval.requested",
    "approval.decided",
    "routine.run_completed",
    "routine.paused",
    "knowledge.ingestion_completed",
    "document.deleted",
    "knowledge.document_changed",
    "memory.fact_proposed",
    "file.ready",
    "quota.warning",
    "quota.exceeded",
    "erasure.completed",
    "audit.event",
    "eval.completed",
    "channel_integration.updated",
    "webhook.test",
    "role.changed",
    "membership.changed",
]

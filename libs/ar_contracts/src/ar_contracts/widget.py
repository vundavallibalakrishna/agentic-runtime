"""Embedded chat contracts. Spec: docs/03-specs/16-channels.md §7."""

import uuid

from pydantic import Field

from ar_contracts.api_model import ApiModel


class WidgetSessionBody(ApiModel):
    integration_id: uuid.UUID
    # The host's signed token. A public widget has no host that knows the visitor, and
    # sends none.
    token: str | None = Field(default=None, min_length=1, max_length=16384)


class WidgetConversationBody(ApiModel):
    agent_id: uuid.UUID


class WidgetMessageBody(ApiModel):
    text: str = Field(min_length=1, max_length=32000)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)
    suggest_followups: bool = False

"""Embedded chat contracts. Spec: docs/03-specs/16-channels.md §7."""

import uuid

from pydantic import Field

from ar_contracts.api_model import ApiModel


class WidgetSessionBody(ApiModel):
    integration_id: uuid.UUID
    token: str = Field(min_length=1, max_length=16384)


class WidgetConversationBody(ApiModel):
    agent_id: uuid.UUID


class WidgetMessageBody(ApiModel):
    text: str = Field(min_length=1, max_length=32000)

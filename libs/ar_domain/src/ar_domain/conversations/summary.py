"""Read and refresh a conversation's rolling summary. The fold is in-process."""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import Any  # noqa: TC003

from ar_common.errors import NotFoundError
from ar_domain.memory.compaction import compact_context, summarise


def read_summary(store: Any, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> dict[str, object]:
    row = _conversation(store, tenant_id, conversation_id)
    return {
        "conversationId": str(conversation_id),
        "summary": str(row.get("rolling_summary") or ""),
        "throughMessageId": str(row.get("summary_through_message_id") or ""),
        "proof": "unit",
    }


def write_summary(
    store: Any, tenant_id: uuid.UUID, conversation_id: uuid.UUID, summary: str
) -> dict[str, object]:
    row = _conversation(store, tenant_id, conversation_id)
    row["rolling_summary"] = summary.strip()
    return read_summary(store, tenant_id, conversation_id)


def refresh_summary(
    store: Any, tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> dict[str, object]:
    """Fold older messages into the stored summary. No model is called."""
    row = _conversation(store, tenant_id, conversation_id)
    messages = [
        item
        for item in store.messages.values()
        if isinstance(item, dict) and item.get("conversation_id") == conversation_id
    ]
    messages.sort(key=lambda item: str(item.get("created_at") or ""))
    packed = compact_context(messages, context_window=200_000, keep_messages=4)
    summary = str(packed.get("summary") or "") or summarise(messages)
    row["rolling_summary"] = summary
    row["summary_through_message_id"] = packed.get("summary_through_message_id") or None
    return read_summary(store, tenant_id, conversation_id)


def _conversation(
    store: Any, tenant_id: uuid.UUID, conversation_id: uuid.UUID
) -> dict[str, object]:
    row = store.conversations.get(conversation_id)
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        raise NotFoundError("conversation not found")
    return row

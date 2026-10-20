"""Transactional outbox. Spec: docs/05-contracts/domain-events.md."""

import uuid
from typing import TYPE_CHECKING, get_args

from sqlalchemy import text

from ar_common.errors import ValidationFailedError
from ar_common.time import utcnow
from ar_contracts.events import PUBLIC_TOPICS, TopicName
from ar_domain.events.models import OutboxEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.db.context import TenantContext

_TOPICS = set(get_args(TopicName))


def known_topic(topic: str) -> str:
    """Reject topics that are not in the contract catalogue."""
    if topic not in _TOPICS:
        raise ValidationFailedError(f"unknown event topic {topic}")
    return topic


def is_public(topic: str) -> bool:
    return topic in PUBLIC_TOPICS


async def emit(
    session: AsyncSession,
    ctx: TenantContext | None,
    topic: str,
    payload: dict[str, object],
) -> OutboxEvent:
    """Insert an outbox row in the caller's transaction."""
    known_topic(topic)
    row = OutboxEvent(
        tenant_id=None if ctx is None else ctx.tenant_id,
        topic=topic,
        payload=payload,
        created_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


async def claim_batch(session: AsyncSession, limit: int) -> list[uuid.UUID]:
    """Claim unpublished rows with ``FOR UPDATE SKIP LOCKED``."""
    result = await session.execute(
        text(
            "SELECT id FROM outbox_events WHERE published_at IS NULL AND attempts < 20 "
            "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT :limit"
        ),
        {"limit": limit},
    )
    return [uuid.UUID(str(row[0])) for row in result]


async def mark_published(session: AsyncSession, event_id: uuid.UUID) -> None:
    await session.execute(
        text("UPDATE outbox_events SET published_at = now() WHERE id = :id"),
        {"id": event_id},
    )


async def mark_attempt(session: AsyncSession, event_id: uuid.UUID, error: str) -> None:
    await session.execute(
        text(
            "UPDATE outbox_events SET attempts = attempts + 1, "
            "payload = payload || jsonb_build_object('_relay_error', :error) "
            "WHERE id = :id"
        ),
        {"id": event_id, "error": error[:500]},
    )

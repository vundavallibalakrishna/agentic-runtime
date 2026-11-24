"""Flush and load ``outbound_webhooks`` and ``webhook_deliveries``.

The tables have existed since revision 0004. This is the path that writes the
rows the API used to keep only in process memory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from ar_common.time import utcnow
from ar_domain.durable.codec import as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession


async def save_outbox(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO outbox_events (
            id, tenant_id, topic, payload, created_at, published_at, attempts
        ) VALUES (
            :id, :tenant_id, :topic, CAST(:payload AS jsonb), :created_at,
            :published_at, :attempts
        )
        ON CONFLICT (id) DO UPDATE SET
            published_at = EXCLUDED.published_at,
            attempts = EXCLUDED.attempts
    """
    for row in rows:
        event_id = as_uuid(row.get("id"))
        if event_id is None:
            continue
        now = utcnow()
        await session.execute(
            text(sql),
            {
                "id": event_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "topic": as_text(row.get("topic"), "webhook.test"),
                "payload": as_json(row.get("payload"), {}),
                "created_at": as_dt(row.get("created_at")) or now,
                "published_at": as_dt(row.get("published_at")),
                "attempts": as_int(row.get("attempts"), 0),
            },
        )


async def save_webhooks(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Insert the secret reference the webhook's foreign key requires, then the webhook."""
    ref_sql = """
        INSERT INTO secret_refs (
            id, tenant_id, name, kind, backend, path, version, description,
            owner_user_id, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :name, 'webhook_secret', 'db_encrypted', :path, 1, '',
            :owner_user_id, :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    sql = """
        INSERT INTO outbound_webhooks (
            id, tenant_id, name, url, secret_ref_id, topics, status,
            created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :name, :url, :secret_ref_id, :topics, :status, :created_by,
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            url = EXCLUDED.url,
            topics = EXCLUDED.topics,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        webhook_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        secret_id = as_uuid(row.get("secret_ref_id"))
        url = as_text(row.get("url"))
        if (
            webhook_id is None
            or tenant_id is None
            or secret_id is None
            or not url.startswith("https://")
        ):
            continue
        now = utcnow()
        owner = as_uuid(row.get("created_by"))
        await session.execute(
            text(ref_sql),
            {
                "id": secret_id,
                "tenant_id": tenant_id,
                "name": f"webhook-{webhook_id}",
                "path": str(secret_id),
                "owner_user_id": owner,
                "created_by": owner,
                "created_at": now,
                "updated_at": now,
            },
        )
        topics = row.get("topics")
        names = [str(item) for item in topics] if isinstance(topics, list) else []
        await session.execute(
            text(sql),
            {
                "id": webhook_id,
                "tenant_id": tenant_id,
                "name": as_text(row.get("name"), "webhook"),
                "url": url,
                "secret_ref_id": secret_id,
                "topics": names,
                "status": as_text(row.get("status"), "active"),
                "created_by": owner,
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_deliveries(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO webhook_deliveries (
            id, tenant_id, webhook_id, target_url, outbox_event_id, status, attempts,
            last_status_code, last_error, next_attempt_at, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :webhook_id, :target_url, :outbox_event_id, :status, :attempts,
            :last_status_code, :last_error, :next_attempt_at, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            attempts = EXCLUDED.attempts,
            last_status_code = EXCLUDED.last_status_code,
            last_error = EXCLUDED.last_error,
            next_attempt_at = EXCLUDED.next_attempt_at,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        delivery_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        event_id = as_uuid(row.get("outbox_event_id"))
        webhook_id = as_uuid(row.get("webhook_id"))
        if None in {delivery_id, tenant_id, event_id} or webhook_id is None:
            continue
        now = utcnow()
        code = row.get("last_status_code")
        await session.execute(
            text(sql),
            {
                "id": delivery_id,
                "tenant_id": tenant_id,
                "webhook_id": webhook_id,
                "target_url": None,
                "outbox_event_id": event_id,
                "status": as_text(row.get("status"), "pending"),
                "attempts": as_int(row.get("attempts"), 0),
                "last_status_code": code if isinstance(code, int) else None,
                "last_error": row.get("last_error")
                if isinstance(row.get("last_error"), str)
                else None,
                "next_attempt_at": as_dt(row.get("next_attempt_at")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )

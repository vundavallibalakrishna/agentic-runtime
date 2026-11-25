"""Flush and hydrate pack rows kept in ``extension_rows``."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any  # noqa: TC003

import orjson
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

_UPSERT = text(
    """
    INSERT INTO extension_rows (
        id, tenant_id, pack_id, bucket, payload, version, reason, created_at, updated_at
    ) VALUES (
        :id, :tenant_id, :pack_id, :bucket, CAST(:payload AS jsonb),
        :version, :reason, now(), now()
    )
    ON CONFLICT (id) DO UPDATE SET
        payload = EXCLUDED.payload,
        bucket = EXCLUDED.bucket,
        version = EXCLUDED.version,
        reason = EXCLUDED.reason,
        updated_at = now()
    """
)

_HISTORY = text(
    """
    INSERT INTO extension_row_versions (
        id, tenant_id, row_id, version, payload, reason, created_at
    ) VALUES (
        :id, :tenant_id, :row_id, :version, CAST(:payload AS jsonb), :reason, now()
    )
    """
)


def _json(value: object) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported extension value {type(value).__name__}")


async def save_extension_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Write dirty pack rows. Deleted rows are removed by the shared deletion pass."""
    for row in rows:
        if row.get("_deleted"):
            continue
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        encoded = orjson.dumps(payload, default=_json).decode()
        version = int(row.get("version") or 1)
        reason = str(row.get("reason") or "")
        await session.execute(
            _UPSERT,
            {
                "id": row.get("id"),
                "tenant_id": row.get("tenant_id"),
                "pack_id": str(row.get("pack_id") or ""),
                "bucket": str(row.get("bucket") or ""),
                "payload": encoded,
                "version": version,
                "reason": reason,
            },
        )
        await session.execute(
            _HISTORY,
            {
                "id": uuid.uuid4(),
                "tenant_id": row.get("tenant_id"),
                "row_id": row.get("id"),
                "version": version,
                "payload": encoded,
                "reason": reason,
            },
        )


async def load_extension_rows(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """Load one tenant's pack rows onto ``store.extension_rows``."""
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    result = await session.execute(
        text("SELECT * FROM extension_rows WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    for row in result.mappings():
        _merge(store, "extension_rows", row["id"], dict(row))

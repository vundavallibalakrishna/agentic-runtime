"""Postgres idempotency keys. The table already exists (revision 0004).

Dev and CI keep the process-local store. Every other environment shares this
table, so a retry that lands on another replica replays the same response.
"""

from __future__ import annotations

import base64
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert

from ar_common.errors import UnavailableError
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.engine import get_engine
from ar_domain.db.session import tenant_session
from ar_domain.events.idempotency import StoredResponse
from ar_domain.events.models import IdempotencyKey


def encode_body(body: bytes | None) -> dict[str, str] | None:
    """JSON-safe form of a stored response body."""
    if body is None:
        return None
    return {"b64": base64.b64encode(body).decode("ascii")}


def decode_body(raw: object) -> bytes | None:
    """Inverse of :func:`encode_body`. A missing or foreign shape is no body."""
    if not isinstance(raw, dict):
        return None
    encoded = raw.get("b64")
    if not isinstance(encoded, str) or not encoded:
        return None
    try:
        return base64.b64decode(encoded)
    except ValueError:
        return None


class PostgresIdempotencyStore:
    """``idempotency_keys`` under the caller's tenant row-level policy."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    async def get(self, key: tuple[str, str, str]) -> StoredResponse | None:
        tenant_id = _tenant(key[0])
        if tenant_id is None:
            return None
        try:
            async with tenant_session(
                _context(tenant_id), engine=get_engine(self.database_url)
            ) as session:
                row = await session.get(IdempotencyKey, (tenant_id, key[1], key[2]))
        except Exception as exc:
            raise UnavailableError("idempotency store is unavailable") from exc
        if row is None:
            return None
        return StoredResponse(
            request_hash=row.request_hash,
            status_code=row.status_code,
            body=decode_body(row.response_body),
        )

    async def put(self, key: tuple[str, str, str], value: StoredResponse) -> None:
        tenant_id = _tenant(key[0])
        if tenant_id is None:
            return
        payload = encode_body(value.body)
        stmt = pg_insert(IdempotencyKey).values(
            tenant_id=tenant_id,
            principal_id=key[1],
            key=key[2],
            request_hash=value.request_hash,
            status_code=value.status_code,
            response_body=payload,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "principal_id", "key"],
            set_={
                "request_hash": value.request_hash,
                "status_code": value.status_code,
                "response_body": payload,
            },
        )
        try:
            async with tenant_session(
                _context(tenant_id), engine=get_engine(self.database_url)
            ) as session:
                await session.execute(stmt)
        except Exception as exc:
            raise UnavailableError("idempotency store is unavailable") from exc


def _tenant(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _context(tenant_id: uuid.UUID) -> TenantContext:
    principal = Principal(
        kind="system",
        id="idempotency",
        tenant_id=tenant_id,
        auth_method="system",
    )
    return TenantContext(
        tenant_id=tenant_id,
        user_id=None,
        principal=principal,
        request_id="idempotency",
    )

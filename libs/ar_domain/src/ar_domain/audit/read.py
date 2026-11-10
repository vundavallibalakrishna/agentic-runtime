"""Read and verify the hash-chained audit log.

The API and the CLI use this module. They do not read the process-local
``audit_log``. Postgres rows are written only by ``audit.service.record``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

from ar_domain.audit.chain import GENESIS, audit_document, chain_hash
from ar_domain.audit.models import AuditEvent
from ar_domain.audit.service import find_broken

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


def seal_chain_row(
    *,
    seq: int,
    prev_hash: str,
    action: str,
    actor_type: str = "user",
    actor_id: str = "user",
    target_type: str = "audit",
    target_id: str | None = None,
    outcome: str = "success",
    detail: dict[str, object] | None = None,
    tenant_id: str | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    """One chained row, using the same document ``audit.service.record`` hashes."""
    from ar_common.time import utcnow  # noqa: PLC0415

    when = occurred_at or utcnow()
    document = audit_document(
        tenant_id=tenant_id,
        tenant_seq=seq,
        occurred_at=when,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        detail={} if detail is None else detail,
        prev_hash=prev_hash,
    )
    return {
        "id": seq,
        "tenant_id": tenant_id,
        "tenant_seq": seq,
        "occurred_at": when,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "outcome": outcome,
        "detail": document["detail"],
        "prev_hash": prev_hash,
        "hash": chain_hash(prev_hash, document),
    }


def verify_public_chain(
    rows: list[dict[str, object]],
    *,
    from_seq: int | None = None,
    to_seq: int | None = None,
) -> dict[str, object]:
    """Recompute the hash chain. A tampered row sets ``broken_at_seq``."""
    chosen = _slice(rows, from_seq, to_seq)
    if not chosen:
        return {
            "ok": True,
            "checked": 0,
            "first_seq": None,
            "last_seq": None,
            "broken_at_seq": None,
        }
    events = [_event(row) for row in chosen]
    found = find_broken(events)
    broken_seq = None
    if found.broken_id is not None:
        match = next((event for event in events if event.id == found.broken_id), None)
        broken_seq = None if match is None else match.tenant_seq
    return {
        "ok": found.ok,
        "checked": found.checked,
        "first_seq": events[0].tenant_seq,
        "last_seq": events[-1].tenant_seq,
        "broken_at_seq": broken_seq,
    }


def chained_only(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Rows that carry both links of the hash chain. Anything else is dropped."""
    return [
        row
        for row in rows
        if (
            isinstance(row, dict)
            and row.get("hash")
            and row.get("prev_hash")
            and row.get("tenant_seq") is not None
        )
    ]


def as_engine(engine: object) -> AsyncEngine | None:
    """The database engine, or None when the process has no Postgres binding."""
    from sqlalchemy.ext.asyncio import AsyncEngine as _AsyncEngine  # noqa: PLC0415

    return engine if isinstance(engine, _AsyncEngine) else None


async def list_chain(session: AsyncSession, tenant_id: uuid.UUID) -> list[dict[str, object]]:
    """The tenant's hash-chained rows, oldest first."""
    result = await session.execute(
        text(
            "SELECT id, tenant_id, tenant_seq, occurred_at, actor_type, actor_id, "
            "action, target_type, target_id, outcome, detail, prev_hash, hash "
            "FROM audit_events WHERE tenant_id = :tenant_id ORDER BY tenant_seq"
        ),
        {"tenant_id": tenant_id},
    )
    return [_public(dict(row._mapping)) for row in result if row._mapping.get("hash")]


async def get_chain_event(
    session: AsyncSession, tenant_id: uuid.UUID, event_id: int
) -> dict[str, object] | None:
    """One chained row in this tenant, or None."""
    result = await session.execute(
        text(
            "SELECT id, tenant_id, tenant_seq, occurred_at, actor_type, actor_id, "
            "action, target_type, target_id, outcome, detail, prev_hash, hash "
            "FROM audit_events WHERE tenant_id = :tenant_id AND id = :event_id"
        ),
        {"tenant_id": tenant_id, "event_id": event_id},
    )
    row = result.mappings().first()
    if row is None or not row.get("hash") or not row.get("prev_hash"):
        return None
    return _public(dict(row))


def genesis() -> str:
    """The hash that starts a tenant chain."""
    return GENESIS


def _slice(
    rows: list[dict[str, object]], start: int | None, end: int | None
) -> list[dict[str, object]]:
    chosen: list[dict[str, object]] = []
    for row in chained_only(rows):
        seq = int(str(row["tenant_seq"]))
        if start is not None and seq < start:
            continue
        if end is not None and seq > end:
            continue
        chosen.append(row)
    return chosen


def _event(row: dict[str, object]) -> AuditEvent:
    when = row.get("occurred_at")
    if isinstance(when, str):
        when = datetime.fromisoformat(when)
    if not isinstance(when, datetime):
        raise TypeError("occurred_at is required")
    tenant = row.get("tenant_id")
    tenant_id = None
    if isinstance(tenant, uuid.UUID):
        tenant_id = tenant
    elif tenant:
        tenant_id = uuid.UUID(str(tenant))
    detail = row.get("detail")
    target = row.get("target_id")
    return AuditEvent(
        id=int(str(row.get("id") or row["tenant_seq"])),
        tenant_id=tenant_id,
        tenant_seq=int(str(row["tenant_seq"])),
        occurred_at=when,
        actor_type=str(row.get("actor_type") or "user"),
        actor_id=str(row.get("actor_id") or ""),
        action=str(row["action"]),
        target_type=str(row.get("target_type") or "audit"),
        target_id=None if target in {None, ""} else str(target),
        outcome=str(row.get("outcome") or "success"),
        detail=detail if isinstance(detail, dict) else {},
        prev_hash=str(row["prev_hash"]),
        hash=str(row["hash"]),
    )


def _public(row: dict[str, object]) -> dict[str, object]:
    public = dict(row)
    tenant = public.get("tenant_id")
    if isinstance(tenant, uuid.UUID):
        public["tenant_id"] = str(tenant)
    return public

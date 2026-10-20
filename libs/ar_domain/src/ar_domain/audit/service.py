"""Append and verify the audit hash chain.

Spec: docs/03-specs/17-audit-usage-metering.md §1.
"""

import uuid  # noqa: TC003
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pydantic import JsonValue
from sqlalchemy import text

from ar_common.redaction import redact
from ar_common.time import utcnow
from ar_domain.audit.actions import AuditAction
from ar_domain.audit.chain import GENESIS, audit_document, chain_hash, json_safe
from ar_domain.audit.models import AuditEvent
from ar_domain.db.session import register_platform_audit_hook

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.db.context import TenantContext


class UnknownAuditActionError(ValueError):
    """Raised when an action is not in the catalogue."""


def parse_action(action: AuditAction | str) -> str:
    """Return the catalogue value or reject an unknown name."""
    if isinstance(action, AuditAction):
        return action.value
    try:
        return AuditAction(action).value
    except ValueError as exc:
        raise UnknownAuditActionError(action) from exc


@dataclass(frozen=True, slots=True)
class ChainReport:
    """Result of walking a tenant chain."""

    ok: bool
    checked: int
    broken_id: int | None


async def _lock_and_tip(session: AsyncSession, tenant_id: uuid.UUID | None) -> tuple[str, int]:
    key = "audit:platform" if tenant_id is None else f"audit:{tenant_id}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": key},
    )
    if tenant_id is None:
        statement = text(
            "SELECT hash, tenant_seq FROM audit_events "
            "WHERE tenant_id IS NULL ORDER BY tenant_seq DESC LIMIT 1"
        )
        params: dict[str, object] = {}
    else:
        statement = text(
            "SELECT hash, tenant_seq FROM audit_events "
            "WHERE tenant_id = :tenant_id ORDER BY tenant_seq DESC LIMIT 1"
        )
        params = {"tenant_id": tenant_id}
    row = (await session.execute(statement, params)).first()
    if row is None:
        return GENESIS, 1
    return str(row[0]), int(row[1]) + 1


async def record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    actor_type: str,
    actor_id: str,
    action: AuditAction | str,
    target_type: str,
    target_id: str | None,
    detail: object | None = None,
    outcome: str = "success",
    on_behalf_of_user_id: uuid.UUID | None = None,
) -> AuditEvent:
    """Append one event under the tenant advisory lock."""
    action_value = parse_action(action)
    redacted = redact({} if detail is None else detail)
    prev_hash, tenant_seq = await _lock_and_tip(session, tenant_id)
    occurred_at = utcnow()
    document = audit_document(
        tenant_id=None if tenant_id is None else str(tenant_id),
        tenant_seq=tenant_seq,
        occurred_at=occurred_at,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action_value,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        detail=redacted,
        prev_hash=prev_hash,
    )
    digest = chain_hash(prev_hash, document)
    stored = json_safe(redacted)
    detail_dict = stored if isinstance(stored, dict) else {}
    row = AuditEvent(
        tenant_id=tenant_id,
        tenant_seq=tenant_seq,
        occurred_at=occurred_at,
        actor_type=actor_type,
        actor_id=actor_id,
        on_behalf_of_user_id=on_behalf_of_user_id,
        action=action_value,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        detail=cast("dict[str, object]", detail_dict),
        prev_hash=prev_hash,
        hash=digest,
    )
    session.add(row)
    await session.flush()
    return row


async def record_for_context(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    action: AuditAction | str,
    target_type: str,
    target_id: str | None,
    detail: object | None = None,
    outcome: str = "success",
) -> AuditEvent:
    """Record an event for the principal bound to ``ctx``."""
    principal = ctx.principal
    return await record(
        session,
        tenant_id=ctx.tenant_id,
        actor_type=principal.kind if principal.kind != "agent" else "agent",
        actor_id=principal.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        outcome=outcome,
    )


def document_for_row(row: AuditEvent) -> dict[str, JsonValue]:
    """Rebuild the hashed document from a stored row."""
    return audit_document(
        tenant_id=None if row.tenant_id is None else str(row.tenant_id),
        tenant_seq=row.tenant_seq,
        occurred_at=row.occurred_at,
        actor_type=row.actor_type,
        actor_id=row.actor_id,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        outcome=row.outcome,
        detail=row.detail,
        prev_hash=row.prev_hash,
    )


def find_broken(rows: list[AuditEvent]) -> ChainReport:
    """Walk rows ordered by ``tenant_seq`` and return the first mismatch."""
    previous = GENESIS
    checked = 0
    for row in rows:
        expected_prev = previous
        if row.prev_hash != expected_prev:
            return ChainReport(ok=False, checked=checked, broken_id=row.id)
        digest = chain_hash(row.prev_hash, document_for_row(row))
        if digest != row.hash:
            return ChainReport(ok=False, checked=checked, broken_id=row.id)
        previous = row.hash
        checked += 1
    return ChainReport(ok=True, checked=checked, broken_id=None)


async def verify_chain(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    start_seq: int = 1,
    end_seq: int | None = None,
) -> ChainReport:
    """Load a slice of the chain and verify it."""
    if tenant_id is None:
        statement = text(
            "SELECT * FROM audit_events WHERE tenant_id IS NULL "
            "AND tenant_seq >= :start AND (:end IS NULL OR tenant_seq <= :end) "
            "ORDER BY tenant_seq"
        )
    else:
        statement = text(
            "SELECT * FROM audit_events WHERE tenant_id = :tenant_id "
            "AND tenant_seq >= :start AND (:end IS NULL OR tenant_seq <= :end) "
            "ORDER BY tenant_seq"
        )
    result = await session.execute(
        statement,
        {"tenant_id": tenant_id, "start": start_seq, "end": end_seq},
    )
    rows = [AuditEvent(**dict(item._mapping)) for item in result]
    return find_broken(rows)


async def write_platform_session(session: AsyncSession, reason: str) -> None:
    """Audit hook for ``platform_session``."""
    await record(
        session,
        tenant_id=None,
        actor_type="system",
        actor_id="platform",
        action=AuditAction.PLATFORM_SESSION_OPENED,
        target_type="platform_session",
        target_id=None,
        detail={"reason": reason},
    )


def install_platform_hook() -> None:
    """Register the platform-session audit hook."""
    register_platform_audit_hook(write_platform_session)

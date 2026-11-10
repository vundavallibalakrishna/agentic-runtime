"""Flush and hydrate standing approvals and review queues.

These rows are durable. Two API replicas see them because each request loads
the tenant and commits the unit. Spec: docs/04-data/schema.md §7 and §21.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from ar_common.time import utcnow
from ar_domain.durable.codec import as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession
_ITEM_STATUSES = frozenset({"pending", "in_review", "signed", "rejected", "expired", "superseded"})
_PREPARERS = frozenset({"user", "service_account", "guest"})


async def save_shared_rows(session: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> None:
    """Write the durable books after tools and agents exist."""
    await save_standing_approvals(session, pending.get("standing_approvals", []))
    await save_review_queues(session, pending.get("review_queues", []))
    await save_review_items(session, pending.get("review_items", []))


async def load_shared_rows(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.m28 import _load  # noqa: PLC0415

    await _load(
        session,
        store,
        "standing_approvals",
        "SELECT * FROM standing_approvals WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session,
        store,
        "review_queues",
        "SELECT * FROM review_queues WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session,
        store,
        "review_items",
        "SELECT * FROM review_items WHERE tenant_id = :tenant_id",
        tenant_id,
    )


async def save_standing_approvals(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO standing_approvals (
            id, tenant_id, granted_by_user_id, agent_id, routine_id, tool_id,
            argument_constraints, max_uses, uses, expires_at, revoked_at, created_at
        ) VALUES (
            :id, :tenant_id, :granted_by_user_id, :agent_id, :routine_id, :tool_id,
            CAST(:argument_constraints AS jsonb), :max_uses, :uses, :expires_at,
            :revoked_at, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            uses = EXCLUDED.uses,
            revoked_at = EXCLUDED.revoked_at,
            expires_at = EXCLUDED.expires_at
    """
    for row in rows:
        standing_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        granted_by = as_uuid(row.get("granted_by_user_id"))
        tool_id = as_uuid(row.get("tool_id"))
        agent_id = as_uuid(row.get("agent_id"))
        routine_id = as_uuid(row.get("routine_id"))
        expires = as_dt(row.get("expires_at"))
        if None in {standing_id, tenant_id, granted_by, tool_id, expires}:
            continue
        if agent_id is None and routine_id is None:
            continue
        if not await _exists(session, "tools", tool_id):
            continue
        if not await _exists(session, "users", granted_by):
            continue
        if agent_id is not None and not await _exists(session, "agents", agent_id):
            continue
        max_uses = row.get("max_uses")
        await _one(
            session,
            sql,
            {
                "id": standing_id,
                "tenant_id": tenant_id,
                "granted_by_user_id": granted_by,
                "agent_id": agent_id,
                "routine_id": routine_id,
                "tool_id": tool_id,
                "argument_constraints": as_json(row.get("argument_constraints"), []),
                "max_uses": max_uses if isinstance(max_uses, int) else None,
                "uses": as_int(row.get("uses"), 0),
                "expires_at": expires,
                "revoked_at": as_dt(row.get("revoked_at")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def save_review_queues(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO review_queues (
            id, tenant_id, slug, name, subject_type, levels, statement_template,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :subject_type, CAST(:levels AS jsonb),
            :statement_template, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            levels = EXCLUDED.levels,
            statement_template = EXCLUDED.statement_template,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        queue_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        subject = as_text(row.get("subject_type"))
        slug = as_text(row.get("slug"))
        if None in {queue_id, tenant_id} or not slug or not subject:
            continue
        if not await _exists(session, "tenants", tenant_id):
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": queue_id,
                "tenant_id": tenant_id,
                "slug": slug,
                "name": as_text(row.get("name"), slug),
                "subject_type": subject,
                "levels": as_json(row.get("levels"), []),
                "statement_template": as_text(row.get("statement_template"), ""),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_review_items(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO review_items (
            id, tenant_id, queue_id, subject_type, subject_id, subject_ref,
            content_hash, statement_text, statement_hash, status, current_level,
            preparer_principal_type, preparer_principal_id, expires_at, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :queue_id, :subject_type, :subject_id, CAST(:subject_ref AS jsonb),
            :content_hash, :statement_text, :statement_hash, :status, :current_level,
            :preparer_principal_type, :preparer_principal_id, :expires_at, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            current_level = EXCLUDED.current_level,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        queue_id = as_uuid(row.get("queue_id"))
        subject_id = as_uuid(row.get("subject_id"))
        preparer = as_uuid(row.get("preparer_principal_id"))
        status = as_text(row.get("status"), "pending")
        kind = as_text(row.get("preparer_principal_type"), "user")
        if None in {item_id, tenant_id, queue_id, subject_id, preparer}:
            continue
        if status not in _ITEM_STATUSES or kind not in _PREPARERS:
            continue
        if not await _exists(session, "review_queues", queue_id):
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "queue_id": queue_id,
                "subject_type": as_text(row.get("subject_type"), "file"),
                "subject_id": subject_id,
                "subject_ref": as_json(row.get("subject_ref"), {}),
                "content_hash": as_text(row.get("content_hash"), "0"),
                "statement_text": as_text(row.get("statement_text"), ""),
                "statement_hash": as_text(row.get("statement_hash"), "0"),
                "status": status,
                "current_level": as_int(row.get("current_level"), 1),
                "preparer_principal_type": kind,
                "preparer_principal_id": preparer,
                "expires_at": as_dt(row.get("expires_at")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _one(session: AsyncSession, sql: str, params: dict[str, Any]) -> None:
    """One insert. A check or foreign-key failure does not abort the rest of the flush."""
    try:
        async with session.begin_nested():
            await session.execute(text(sql), params)
    except DBAPIError, IntegrityError:
        return


async def _exists(session: AsyncSession, table: str, row_id: object) -> bool:
    # The table name is one of a fixed set chosen by the callers above.
    result = await session.execute(
        text(f"SELECT 1 FROM {table} WHERE id = :id"),  # noqa: S608
        {"id": row_id},
    )
    return result.first() is not None

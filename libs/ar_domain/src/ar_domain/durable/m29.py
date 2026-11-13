"""Flush and hydrate agent API keys, grants, idempotency and A2A tasks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from ar_domain.durable.codec import as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def save_exposure(session: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> None:
    await _keys(session, pending.get("agent_api_keys", []))
    await _idempotency(session, pending.get("agent_api_idempotency", []))
    await _grants(session, pending.get("agent_api_grants", []))
    await _tasks(session, pending.get("a2a_tasks", []))


async def load_exposure(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    # Idempotency rows are not loaded for every request: they grow with every idempotent
    # call and are read by their unique (key_id, idempotency_key) through
    # ``exposure.runs._idempotency_row_db``. See OQ-136.
    queries = (
        ("agent_api_keys", "SELECT * FROM agent_api_keys WHERE tenant_id = :tenant_id"),
        ("agent_api_grants", "SELECT * FROM agent_api_grants WHERE tenant_id = :tenant_id"),
        ("a2a_tasks", "SELECT * FROM a2a_tasks WHERE tenant_id = :tenant_id"),
    )
    for name, sql in queries:
        result = await session.execute(text(sql), {"tenant_id": tenant_id})
        for row in result.mappings():
            _merge(store, name, row["id"], dict(row))


async def _keys(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO agent_api_keys (
            id, tenant_id, agent_id, created_by_user_id, label, prefix, secret_hash, scope,
            rate_limit_rpm, monthly_quota, month_stamp, month_count, last_used_at, revoked_at,
            rotated_from_id, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :agent_id, :created_by_user_id, :label, :prefix, :secret_hash, :scope,
            :rate_limit_rpm, :monthly_quota, :month_stamp, :month_count, :last_used_at, :revoked_at,
            :rotated_from_id, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            label = EXCLUDED.label,
            scope = EXCLUDED.scope,
            rate_limit_rpm = EXCLUDED.rate_limit_rpm,
            monthly_quota = EXCLUDED.monthly_quota,
            month_stamp = EXCLUDED.month_stamp,
            month_count = EXCLUDED.month_count,
            last_used_at = EXCLUDED.last_used_at,
            revoked_at = EXCLUDED.revoked_at,
            rotated_from_id = EXCLUDED.rotated_from_id,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        key_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        agent_id = as_uuid(row.get("agent_id"))
        user_id = as_uuid(row.get("created_by_user_id"))
        if None in {key_id, tenant_id, agent_id, user_id}:
            continue
        scope = as_text(row.get("scope"), "agent")
        if scope not in {"agent", "workspace"}:
            scope = "agent"
        await session.execute(
            text(sql),
            {
                "id": key_id,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "created_by_user_id": user_id,
                "label": as_text(row.get("label"), "key")[:80],
                "prefix": as_text(row.get("prefix")),
                "secret_hash": as_text(row.get("secret_hash")),
                "scope": scope,
                "rate_limit_rpm": as_int(row.get("rate_limit_rpm"), 60),
                "monthly_quota": as_int(row.get("monthly_quota"), 10000),
                "month_stamp": as_text(row.get("month_stamp")),
                "month_count": as_int(row.get("month_count"), 0),
                "last_used_at": as_dt(row.get("last_used_at")),
                "revoked_at": as_dt(row.get("revoked_at")),
                "rotated_from_id": as_uuid(row.get("rotated_from_id")),
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
            },
        )


async def _idempotency(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO agent_api_idempotency (
            id, tenant_id, key_id, idempotency_key, request_hash, status_code, response,
            run_id, state, created_at
        ) VALUES (
            :id, :tenant_id, :key_id, :idempotency_key, :request_hash, :status_code,
            CAST(:response AS jsonb), :run_id, :state, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            request_hash = EXCLUDED.request_hash,
            status_code = EXCLUDED.status_code,
            response = EXCLUDED.response,
            run_id = EXCLUDED.run_id,
            state = EXCLUDED.state
    """
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        key_id = as_uuid(row.get("key_id"))
        if None in {item_id, tenant_id, key_id}:
            continue
        state = as_text(row.get("state"), "completed")
        if state not in {"in_flight", "completed"}:
            state = "completed"
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "key_id": key_id,
                "idempotency_key": as_text(row.get("idempotency_key"))[:255],
                "request_hash": as_text(row.get("request_hash")),
                "status_code": as_int(row.get("status_code"), 200),
                "response": as_json(row.get("response"), {}),
                "run_id": as_uuid(row.get("run_id")),
                "state": state,
                "created_at": as_dt(row.get("created_at")),
            },
        )


async def _grants(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO agent_api_grants (
            id, tenant_id, key_id, agent_id, conversation_id, run_id, created_at
        ) VALUES (
            :id, :tenant_id, :key_id, :agent_id, :conversation_id, :run_id, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET run_id = EXCLUDED.run_id
    """
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        key_id = as_uuid(row.get("key_id"))
        agent_id = as_uuid(row.get("agent_id"))
        conversation_id = as_uuid(row.get("conversation_id"))
        if None in {item_id, tenant_id, key_id, agent_id, conversation_id}:
            continue
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "key_id": key_id,
                "agent_id": agent_id,
                "conversation_id": conversation_id,
                "run_id": as_uuid(row.get("run_id")),
                "created_at": as_dt(row.get("created_at")),
            },
        )


async def _tasks(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO a2a_tasks (
            id, tenant_id, agent_id, key_id, conversation_id, run_id, state, output_text,
            artifacts, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :agent_id, :key_id, :conversation_id, :run_id, :state, :output_text,
            CAST(:artifacts AS jsonb), :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            state = EXCLUDED.state,
            output_text = EXCLUDED.output_text,
            artifacts = EXCLUDED.artifacts,
            run_id = EXCLUDED.run_id,
            updated_at = EXCLUDED.updated_at
    """
    allowed = {"submitted", "working", "completed", "failed", "canceled", "input-required"}
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        agent_id = as_uuid(row.get("agent_id"))
        key_id = as_uuid(row.get("key_id"))
        conversation_id = as_uuid(row.get("conversation_id"))
        if None in {item_id, tenant_id, agent_id, key_id, conversation_id}:
            continue
        state = as_text(row.get("state"), "submitted")
        if state not in allowed:
            state = "submitted"
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "key_id": key_id,
                "conversation_id": conversation_id,
                "run_id": as_uuid(row.get("run_id")),
                "state": state,
                "output_text": as_text(row.get("output_text")),
                "artifacts": as_json(row.get("artifacts"), []),
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
            },
        )

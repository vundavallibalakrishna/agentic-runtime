"""Flush and hydrate service connections, data connections and model catalogue."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ar_common.time import utcnow
from ar_domain.durable.codec import as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    from typing import Any


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _bytea(value: object) -> bytes:
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytes):
        return value
    return b""


async def _one(session: AsyncSession, sql: str, params: dict[str, object]) -> None:
    await session.execute(text(sql), params)


async def save_service_connections(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO service_connections (
            id, tenant_id, owner_user_id, name, kind, status, header_name, username,
            token_url, authorize_url, client_id, scopes, probe_url, secret, access_token,
            refresh_token, expires_at, last_tested_at, last_error, version, created_at,
            updated_at
        ) VALUES (
            :id, :tenant_id, :owner_user_id, :name, :kind, :status, :header_name, :username,
            :token_url, :authorize_url, :client_id, CAST(:scopes AS jsonb), :probe_url, :secret,
            :access_token, :refresh_token, :expires_at, :last_tested_at, :last_error, :version,
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            header_name = EXCLUDED.header_name,
            username = EXCLUDED.username,
            token_url = EXCLUDED.token_url,
            authorize_url = EXCLUDED.authorize_url,
            client_id = EXCLUDED.client_id,
            scopes = EXCLUDED.scopes,
            probe_url = EXCLUDED.probe_url,
            secret = EXCLUDED.secret,
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            last_tested_at = EXCLUDED.last_tested_at,
            last_error = EXCLUDED.last_error,
            version = EXCLUDED.version,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        connection_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        owner_id = as_uuid(row.get("owner_user_id"))
        if connection_id is None or tenant_id is None or owner_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": connection_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_id,
                "name": as_text(row.get("name"), "connection"),
                "kind": as_text(row.get("kind"), "bearer"),
                "status": as_text(row.get("status"), "active"),
                "header_name": as_text(row.get("header_name")),
                "username": as_text(row.get("username")),
                "token_url": as_text(row.get("token_url")),
                "authorize_url": as_text(row.get("authorize_url")),
                "client_id": as_text(row.get("client_id")),
                "scopes": as_json(row.get("scopes"), []),
                "probe_url": as_text(row.get("probe_url")),
                "secret": _bytea(row.get("secret")),
                "access_token": _bytea(row.get("access_token")),
                "refresh_token": _bytea(row.get("refresh_token")),
                "expires_at": _optional(row.get("expires_at")),
                "last_tested_at": as_dt(row.get("last_tested_at")),
                "last_error": _optional(row.get("last_error")),
                "version": as_int(row.get("version"), 1),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_data_connections(
    session: AsyncSession, store: object, rows: list[dict[str, Any]]
) -> None:
    """Persist a data connection. The DSN is ciphertext, not a column of plaintext."""
    from ar_domain.secrets.crypto import seal  # noqa: PLC0415
    from ar_domain.tools.service_connections import connection_key  # noqa: PLC0415

    ref_sql = """
        INSERT INTO secret_refs (
            id, tenant_id, name, kind, backend, path, version, description,
            owner_user_id, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :name, 'db_dsn', 'db_encrypted', :path, 1, '',
            :owner_user_id, :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    sql = """
        INSERT INTO data_connections (
            id, tenant_id, name, engine, dsn_secret_ref_id, identity_mode, allowlist,
            row_limit, statement_timeout_s, classification, schema_notes, status,
            dsn_ciphertext, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :name, :engine, :dsn_secret_ref_id, :identity_mode,
            CAST(:allowlist AS jsonb), :row_limit, :statement_timeout_s, :classification,
            :schema_notes, :status, :dsn_ciphertext, :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            allowlist = EXCLUDED.allowlist,
            row_limit = EXCLUDED.row_limit,
            statement_timeout_s = EXCLUDED.statement_timeout_s,
            schema_notes = EXCLUDED.schema_notes,
            status = EXCLUDED.status,
            dsn_ciphertext = EXCLUDED.dsn_ciphertext,
            updated_at = EXCLUDED.updated_at
    """
    secrets = getattr(store, "secret_values", {})
    for row in rows:
        connection_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        secret_id = as_uuid(row.get("dsn_secret_ref_id"))
        if connection_id is None or tenant_id is None or secret_id is None:
            continue
        now = utcnow()
        owner = as_uuid(row.get("created_by"))
        await _one(
            session,
            ref_sql,
            {
                "id": secret_id,
                "tenant_id": tenant_id,
                "name": f"data-dsn-{connection_id}",
                "path": str(secret_id),
                "owner_user_id": owner,
                "created_by": owner,
                "created_at": now,
                "updated_at": now,
            },
        )
        ciphertext = _bytea(row.get("dsn_ciphertext"))
        if not ciphertext and isinstance(secrets, dict):
            raw = secrets.get(secret_id)
            if isinstance(raw, bytes) and raw and not raw.startswith(b"memory:"):
                ciphertext = seal(connection_key(), raw)
        await _one(
            session,
            sql,
            {
                "id": connection_id,
                "tenant_id": tenant_id,
                "name": as_text(row.get("name"), "database"),
                "engine": as_text(row.get("engine"), "postgres"),
                "dsn_secret_ref_id": secret_id,
                "identity_mode": as_text(row.get("identity_mode"), "service"),
                "allowlist": as_json(row.get("allowlist"), {}),
                "row_limit": as_int(row.get("row_limit"), 1000),
                "statement_timeout_s": as_int(row.get("statement_timeout_s"), 30),
                "classification": as_text(row.get("classification"), "internal"),
                "schema_notes": as_text(row.get("schema_notes")),
                "status": as_text(row.get("status"), "active"),
                "dsn_ciphertext": ciphertext,
                "created_by": owner,
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def load_service_connections(
    session: AsyncSession, store: object, tenant_id: uuid.UUID
) -> None:
    from ar_domain.durable.hydrate import _merge, _rows  # noqa: PLC0415

    result = await _rows(
        session, "SELECT * FROM service_connections WHERE tenant_id = :tenant_id", tenant_id
    )
    for row in result:
        for key in ("secret", "access_token", "refresh_token"):
            row[key] = _bytea(row.get(key))
        if row.get("expires_at") is not None:
            row["expires_at"] = str(row["expires_at"])
        _merge(store, "service_connections", row["id"], row)


async def load_data_connections(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.hydrate import _merge, _rows  # noqa: PLC0415
    from ar_domain.secrets.crypto import open_sealed  # noqa: PLC0415
    from ar_domain.tools.service_connections import connection_key  # noqa: PLC0415

    secrets = getattr(store, "secret_values", None)
    if not isinstance(secrets, dict):
        return
    for row in await _rows(
        session, "SELECT * FROM data_connections WHERE tenant_id = :tenant_id", tenant_id
    ):
        blob = _bytea(row.get("dsn_ciphertext"))
        row["dsn_ciphertext"] = blob
        secret_id = row.get("dsn_secret_ref_id")
        if blob and isinstance(secret_id, uuid.UUID):
            try:
                secrets[secret_id] = open_sealed(connection_key(), blob)
            except Exception:  # noqa: BLE001 — a bad blob is not a usable DSN
                secrets.pop(secret_id, None)
        _merge(store, "data_connections", row["id"], row)


async def load_model_catalog(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """Registered models survive a restart, including the encrypted provider key."""
    del session
    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine):
        return
    from ar_domain.models.registry import load_registry  # noqa: PLC0415

    await load_registry(engine, store, tenant_id, with_keys=True)

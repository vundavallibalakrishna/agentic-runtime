"""Flush and hydrate connector installs, OAuth grants, OAuth state and named secrets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from ar_common.time import utcnow
from ar_domain.durable.codec import as_dt, as_json, as_text, as_uuid
from ar_domain.secrets.crypto import open_sealed, seal
from ar_domain.tools.service_connections import connection_key

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


def _bytea(value: object) -> bytes:
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytes):
        return value
    return b""


def _seal_text(value: object) -> bytes:
    if not isinstance(value, str) or not value:
        return b""
    return seal(connection_key(), value.encode())


def _open_text(value: object) -> str:
    blob = _bytea(value)
    if not blob:
        return ""
    try:
        return open_sealed(connection_key(), blob).decode()
    except Exception:  # noqa: BLE001 — a bad blob must not drop the rest of the tenant
        return ""


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


async def _one(session: AsyncSession, sql: str, params: dict[str, object]) -> None:
    await session.execute(text(sql), params)


async def save_connector_installs(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO connector_installs (
            id, tenant_id, owner_user_id, slug, connection_name, connection_id, status,
            disabled_tools, config, last_tested_at, last_error, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :owner_user_id, :slug, :connection_name, :connection_id, :status,
            CAST(:disabled_tools AS jsonb), CAST(:config AS jsonb), :last_tested_at, :last_error,
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            connection_name = EXCLUDED.connection_name,
            connection_id = EXCLUDED.connection_id,
            status = EXCLUDED.status,
            disabled_tools = EXCLUDED.disabled_tools,
            config = EXCLUDED.config,
            last_tested_at = EXCLUDED.last_tested_at,
            last_error = EXCLUDED.last_error,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        install_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        owner_id = as_uuid(row.get("owner_user_id"))
        if install_id is None or tenant_id is None or owner_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": install_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_id,
                "slug": as_text(row.get("slug"), "connector"),
                "connection_name": as_text(row.get("connection_name")),
                "connection_id": as_uuid(row.get("connection_id")),
                "status": as_text(row.get("status"), "installed"),
                "disabled_tools": as_json(row.get("disabled_tools"), []),
                "config": as_json(row.get("config"), {}),
                "last_tested_at": as_dt(row.get("last_tested_at")),
                "last_error": row.get("last_error")
                if isinstance(row.get("last_error"), str)
                else None,
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_credential_providers(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO credential_providers (
            id, tenant_id, slug, name, kind, authorize_url, token_url, client_id,
            client_secret_ref_id, default_scopes, token_exchange_audience, extra, status,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :kind, :authorize_url, :token_url, :client_id,
            :client_secret_ref_id, :default_scopes, :token_exchange_audience,
            CAST(:extra AS jsonb), :status, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            authorize_url = EXCLUDED.authorize_url,
            token_url = EXCLUDED.token_url,
            client_id = EXCLUDED.client_id,
            default_scopes = EXCLUDED.default_scopes,
            extra = EXCLUDED.extra,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        provider_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if provider_id is None or tenant_id is None or not row.get("slug"):
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": provider_id,
                "tenant_id": tenant_id,
                "slug": as_text(row.get("slug")),
                "name": as_text(row.get("name"), as_text(row.get("slug"))),
                "kind": as_text(row.get("kind"), "oauth2"),
                "authorize_url": row.get("authorize_url") if row.get("authorize_url") else None,
                "token_url": row.get("token_url") if row.get("token_url") else None,
                "client_id": row.get("client_id") if row.get("client_id") else None,
                "client_secret_ref_id": as_uuid(row.get("client_secret_ref_id")),
                "default_scopes": _strings(row.get("default_scopes")),
                "token_exchange_audience": row.get("token_exchange_audience") or None,
                "extra": as_json(row.get("extra"), {}),
                "status": as_text(row.get("status"), "active"),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_credential_grants(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO credential_grants (
            id, tenant_id, user_id, provider_id, scopes, secret_ref_id, status,
            external_account_label, expires_at, last_used_at, access_ciphertext,
            refresh_ciphertext, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :user_id, :provider_id, :scopes, :secret_ref_id, :status,
            :external_account_label, :expires_at, :last_used_at, :access_ciphertext,
            :refresh_ciphertext, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            scopes = EXCLUDED.scopes,
            status = EXCLUDED.status,
            external_account_label = EXCLUDED.external_account_label,
            expires_at = EXCLUDED.expires_at,
            last_used_at = EXCLUDED.last_used_at,
            access_ciphertext = EXCLUDED.access_ciphertext,
            refresh_ciphertext = EXCLUDED.refresh_ciphertext,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        grant_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        user_id = as_uuid(row.get("user_id"))
        provider_id = as_uuid(row.get("provider_id"))
        if None in {grant_id, tenant_id, user_id, provider_id}:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": grant_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "provider_id": provider_id,
                "scopes": _strings(row.get("scopes")),
                "secret_ref_id": as_uuid(row.get("secret_ref_id")),
                "status": as_text(row.get("status"), "active"),
                "external_account_label": row.get("external_account_label") or None,
                "expires_at": as_dt(row.get("expires_at")),
                "last_used_at": as_dt(row.get("last_used_at")),
                "access_ciphertext": _seal_text(row.get("access_token")),
                "refresh_ciphertext": _seal_text(row.get("refresh_token")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_oauth_states(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO oauth_states (
            id, tenant_id, user_id, provider_id, connection_id, kind, verifier, created_at
        ) VALUES (
            :id, :tenant_id, :user_id, :provider_id, :connection_id, :kind, :verifier, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            verifier = EXCLUDED.verifier,
            kind = EXCLUDED.kind
    """
    for row in rows:
        state = as_text(row.get("id") or "")
        tenant_id = as_uuid(row.get("tenant_id"))
        user_id = as_uuid(row.get("user_id"))
        if not state or tenant_id is None or user_id is None:
            continue
        await _one(
            session,
            sql,
            {
                "id": state,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "provider_id": as_uuid(row.get("provider_id")),
                "connection_id": as_uuid(row.get("connection_id")),
                "kind": as_text(row.get("kind")),
                "verifier": _seal_text(row.get("verifier")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def save_named_secrets(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO named_secrets (id, tenant_id, name, ciphertext, created_at, updated_at)
        VALUES (:id, :tenant_id, :name, :ciphertext, :created_at, :updated_at)
        ON CONFLICT (id) DO UPDATE SET
            ciphertext = EXCLUDED.ciphertext,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        secret_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        name = as_text(row.get("name"))
        if secret_id is None or tenant_id is None or not name:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": secret_id,
                "tenant_id": tenant_id,
                "name": name,
                "ciphertext": _bytea(row.get("ciphertext")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _rows(session: AsyncSession, sql: str, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), {"tenant_id": tenant_id})
    return [dict(item) for item in result.mappings()]


async def load_connector_rows(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    for row in await _rows(
        session, "SELECT * FROM connector_installs WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "connector_installs", row["id"], dict(row))
    for row in await _rows(
        session, "SELECT * FROM credential_providers WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "credential_providers", row["id"], dict(row))
    for row in await _rows(
        session, "SELECT * FROM credential_grants WHERE tenant_id = :tenant_id", tenant_id
    ):
        loaded = dict(row)
        loaded["access_token"] = _open_text(loaded.get("access_ciphertext"))
        loaded["refresh_token"] = _open_text(loaded.get("refresh_ciphertext"))
        loaded.pop("access_ciphertext", None)
        loaded.pop("refresh_ciphertext", None)
        _merge(store, "credential_grants", row["id"], loaded)
    for row in await _rows(
        session, "SELECT * FROM oauth_states WHERE tenant_id = :tenant_id", tenant_id
    ):
        loaded = dict(row)
        loaded["verifier"] = _open_text(loaded.get("verifier"))
        _merge(store, "oauth_states", row["id"], loaded)
    for row in await _rows(
        session, "SELECT * FROM named_secrets WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "named_secrets", row["id"], dict(row))

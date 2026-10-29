"""Persist model providers and resolve a live upstream.

The API process and the model gateway do not share memory. An operator
registers a provider in the product; this module writes the row and stores
the API key in the encrypted secret store. The gateway reads that row when a
chat completion names the upstream model.

Spec: docs/03-specs/04-model-gateway.md.
"""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from ar_common.errors import ArError, ConflictError, ErrorCode
from ar_common.settings import get_settings
from ar_domain.audit.actions import AuditAction
from ar_domain.audit.service import record
from ar_domain.db.engine import platform_database_url
from ar_domain.models.tables import Model, ModelAlias, ModelProvider
from ar_domain.secrets.crypto import parse_keyring
from ar_domain.secrets.stores.db_encrypted import DbEncryptedStore

if TYPE_CHECKING:
    from typing import Any


class _Engines:
    current: AsyncEngine | None = None


_ACTORS = frozenset({"user", "service_account", "agent", "system", "platform_admin"})


@dataclass(frozen=True, slots=True)
class UpstreamTarget:
    """One registered non-fake model the gateway can call."""

    base_url: str
    api_key: str
    upstream_model: str
    timeout_s: int
    kind: str


def _secret_path(tenant_id: uuid.UUID, secret_id: uuid.UUID) -> str:
    return f"tenants/{tenant_id}/secrets/{secret_id}"


def _secret_aad(tenant_id: uuid.UUID, secret_id: uuid.UUID) -> bytes:
    return f"{tenant_id}:{secret_id}".encode()


def _keyring() -> tuple[dict[str, bytes], str]:
    settings = get_settings()
    ring = parse_keyring(settings.db_encryption_keys.get_secret_value())
    active = settings.db_encryption_active_key
    if not ring or active not in ring:
        raise ArError(ErrorCode.VALIDATION_FAILED, "encryption key ring is not configured")
    return ring, active


def _actor(actor_type: str) -> str:
    return actor_type if actor_type in _ACTORS else "user"


def _as_int(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return int(value)


async def save_provider(
    engine: AsyncEngine | None,
    row: dict[str, object],
    *,
    api_key: str | None,
    actor_id: str,
    actor_type: str = "user",
) -> None:
    """Write the provider. A tenant API key is encrypted and never returned."""
    if engine is None:
        return
    tenant_id = row.get("tenant_id")
    if api_key and not isinstance(tenant_id, uuid.UUID):
        raise ArError(ErrorCode.VALIDATION_FAILED, "a platform provider cannot store an API key")
    provider_id = row["id"]
    if not isinstance(provider_id, uuid.UUID):
        provider_id = uuid.UUID(str(provider_id))
    secret_id: uuid.UUID | None = None
    ring: dict[str, bytes] = {}
    active = ""
    if api_key and isinstance(tenant_id, uuid.UUID):
        ring, active = _keyring()
        secret_id = uuid.uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        if api_key and isinstance(tenant_id, uuid.UUID) and secret_id is not None:
            path = _secret_path(tenant_id, secret_id)
            await session.execute(
                text(
                    """
                    INSERT INTO secret_refs (
                        id, tenant_id, name, kind, backend, path, version, description
                    ) VALUES (
                        :id, :tenant_id, :name, 'api_key', 'db_encrypted', :path, 1,
                        'model provider API key'
                    )
                    """
                ),
                {
                    "id": secret_id,
                    "tenant_id": tenant_id,
                    "name": f"model-provider-{provider_id}",
                    "path": path,
                },
            )
            store = DbEncryptedStore(
                session, tenant_id=tenant_id, keyring=ring, active_key_id=active
            )
            await store.put(path, api_key.encode(), aad=_secret_aad(tenant_id, secret_id))
        await _upsert_provider(session, provider_id, row, secret_id)
        await record(
            session,
            tenant_id=tenant_id if isinstance(tenant_id, uuid.UUID) else None,
            actor_type=_actor(actor_type),
            actor_id=actor_id,
            action=AuditAction.MODEL_PROVIDER_CREATED,
            target_type="model_provider",
            target_id=str(provider_id),
            detail={"name": row.get("name"), "kind": row.get("kind")},
        )
    if api_key:
        row["has_api_key"] = True
        row.pop("api_key", None)


async def save_model(
    engine: AsyncEngine | None,
    row: dict[str, object],
    *,
    actor_id: str,
    actor_type: str = "user",
) -> None:
    """Insert a model row and audit ``model.created``."""
    if engine is None:
        return
    model_id = uuid.UUID(str(row["id"]))
    tenant_id = row.get("tenant_id")
    owner = tenant_id if isinstance(tenant_id, uuid.UUID) else None
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        existing = await session.get(Model, model_id)
        if existing is None:
            session.add(
                Model(
                    id=model_id,
                    tenant_id=owner,
                    provider_id=uuid.UUID(str(row["provider_id"])),
                    name=str(row.get("name") or ""),
                    upstream_model=str(row.get("upstream_model") or row.get("name") or ""),
                    kind=str(row.get("kind") or "chat"),
                    capabilities=["streaming", "tools"],
                    price_input_micros_per_mtok=0,
                    price_output_micros_per_mtok=0,
                    licence="",
                    status="active",
                )
            )
        else:
            existing.upstream_model = str(row.get("upstream_model") or existing.upstream_model)
            existing.name = str(row.get("name") or existing.name)
        await record(
            session,
            tenant_id=owner,
            actor_type=_actor(actor_type),
            actor_id=actor_id,
            action=AuditAction.MODEL_CREATED,
            target_type="model",
            target_id=str(model_id),
            detail={"name": row.get("name"), "upstream_model": row.get("upstream_model")},
        )


async def save_alias(
    engine: AsyncEngine | None,
    row: dict[str, object],
    *,
    actor_id: str,
    actor_type: str = "user",
) -> None:
    """Insert or retarget an alias and audit the change."""
    if engine is None:
        return
    alias_id = uuid.UUID(str(row["id"]))
    tenant_id = row.get("tenant_id")
    owner = tenant_id if isinstance(tenant_id, uuid.UUID) else None
    primary = uuid.UUID(str(row["primary_model_id"]))
    name = str(row.get("alias") or "")
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            existing = await session.get(ModelAlias, alias_id)
            action = (
                AuditAction.MODEL_ALIAS_UPDATED
                if existing is not None
                else AuditAction.MODEL_ALIAS_CREATED
            )
            if existing is None:
                prior = await session.scalar(
                    select(ModelAlias).where(
                        ModelAlias.alias == name, ModelAlias.tenant_id == owner
                    )
                )
                if prior is not None:
                    raise ConflictError("a model alias with that name already exists")
                session.add(
                    ModelAlias(
                        id=alias_id,
                        tenant_id=owner,
                        alias=name,
                        kind=str(row.get("kind") or "chat"),
                        primary_model_id=primary,
                        fallback_model_ids=[],
                        traffic_split={},
                        default_params={"temperature": 0.2},
                        status="active",
                    )
                )
            else:
                existing.primary_model_id = primary
            await record(
                session,
                tenant_id=owner,
                actor_type=_actor(actor_type),
                actor_id=actor_id,
                action=action,
                target_type="model_alias",
                target_id=str(alias_id),
                detail={"alias": name},
            )
    except IntegrityError as exc:
        raise ConflictError("a model alias with that name already exists") from exc


async def read_api_key(engine: AsyncEngine, provider_id: uuid.UUID) -> str:
    """Return the provider key. Callers must not log or return it."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        provider = await session.get(ModelProvider, provider_id)
        if provider is None or provider.api_key_ref_id is None or provider.tenant_id is None:
            return ""
        ref = (
            (
                await session.execute(
                    text("SELECT id, path FROM secret_refs WHERE id = :id"),
                    {"id": provider.api_key_ref_id},
                )
            )
            .mappings()
            .first()
        )
        if ref is None:
            return ""
        ring, active = _keyring()
        store = DbEncryptedStore(
            session, tenant_id=provider.tenant_id, keyring=ring, active_key_id=active
        )
        secret_id = ref["id"]
        if not isinstance(secret_id, uuid.UUID):
            secret_id = uuid.UUID(str(secret_id))
        value = await store.get(str(ref["path"]), aad=_secret_aad(provider.tenant_id, secret_id))
        return value.decode()


async def load_into(engine: AsyncEngine, store: Any) -> None:
    """Merge database providers, models and aliases into the process cache."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        providers = (await session.scalars(select(ModelProvider))).all()
        models = (await session.scalars(select(Model))).all()
        aliases = (await session.scalars(select(ModelAlias))).all()
    for provider in providers:
        store.providers[provider.id] = {
            "id": provider.id,
            "tenant_id": provider.tenant_id,
            "name": provider.name,
            "kind": provider.kind,
            "base_url": provider.base_url,
            "status": provider.status,
            "timeout_s": provider.timeout_s,
            "health": provider.health or {},
            "platform": provider.tenant_id is None,
            "has_api_key": provider.api_key_ref_id is not None,
        }
    for model in models:
        store.models[model.id] = {
            "id": model.id,
            "tenant_id": model.tenant_id,
            "provider_id": model.provider_id,
            "name": model.name,
            "upstream_model": model.upstream_model,
            "kind": model.kind,
            "capabilities": list(model.capabilities or []),
            "status": model.status,
            "platform": model.tenant_id is None,
        }
    for alias in aliases:
        store.aliases[alias.id] = {
            "id": alias.id,
            "tenant_id": alias.tenant_id,
            "alias": alias.alias,
            "kind": alias.kind,
            "primary_model_id": alias.primary_model_id,
            "fallback_model_ids": list(alias.fallback_model_ids or []),
            "default_params": dict(alias.default_params or {}),
            "status": alias.status,
            "platform": alias.tenant_id is None,
        }


async def lookup_upstream(model_name: str) -> UpstreamTarget | None:
    """Find a non-fake provider for ``model_name``. Fake names never touch the database."""
    if not model_name or model_name.startswith("fake"):
        return None
    engine = _shared_engine()
    if engine is None:
        return None
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            found = (
                (
                    await session.execute(
                        text(
                            """
                        SELECT p.id, p.base_url, p.kind, p.timeout_s, m.upstream_model
                        FROM models m
                        JOIN model_providers p ON p.id = m.provider_id
                        WHERE m.upstream_model = :name
                          AND m.status = 'active'
                          AND p.status = 'active'
                          AND p.kind <> 'fake'
                        ORDER BY p.tenant_id NULLS LAST
                        LIMIT 1
                        """
                        ),
                        {"name": model_name},
                    )
                )
                .mappings()
                .first()
            )
    except Exception:  # noqa: BLE001 — a down database must not crash the gateway
        return None
    if found is None:
        return None
    provider_id = found["id"]
    if not isinstance(provider_id, uuid.UUID):
        provider_id = uuid.UUID(str(provider_id))
    key = ""
    try:
        key = await read_api_key(engine, provider_id)
    except Exception:  # noqa: BLE001 — a missing key is an upstream failure, not a crash
        key = ""
    return UpstreamTarget(
        base_url=str(found["base_url"]),
        api_key=key,
        upstream_model=str(found["upstream_model"]),
        timeout_s=int(found["timeout_s"] or 120),
        kind=str(found["kind"]),
    )


def _shared_engine() -> AsyncEngine | None:
    if _Engines.current is not None:
        return _Engines.current
    try:
        url = platform_database_url()
    except Exception:  # noqa: BLE001
        return None
    if not url:
        return None
    _Engines.current = create_async_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"timeout": 2, "statement_cache_size": 0},
    )
    return _Engines.current


async def _upsert_provider(
    session: AsyncSession,
    provider_id: uuid.UUID,
    row: dict[str, object],
    secret_id: uuid.UUID | None,
) -> None:
    tenant_id = row.get("tenant_id")
    owner = tenant_id if isinstance(tenant_id, uuid.UUID) else None
    existing = await session.get(ModelProvider, provider_id)
    if existing is None:
        session.add(
            ModelProvider(
                id=provider_id,
                tenant_id=owner,
                name=str(row.get("name") or ""),
                kind=str(row.get("kind") or "openai_compatible"),
                base_url=str(row.get("base_url") or ""),
                api_key_ref_id=secret_id,
                headers={},
                timeout_s=_as_int(row.get("timeout_s"), 120),
                max_concurrency=64,
                status="active",
                health={},
            )
        )
        return
    existing.name = str(row.get("name") or existing.name)
    existing.kind = str(row.get("kind") or existing.kind)
    existing.base_url = str(row.get("base_url") or existing.base_url)
    if secret_id is not None:
        existing.api_key_ref_id = secret_id

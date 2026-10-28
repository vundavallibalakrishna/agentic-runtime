"""Attach a process cache to Postgres when the database is up."""

import asyncio
import os
import sys
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from ar_common.logging import get_logger
from ar_domain.db.engine import platform_database_url
from ar_domain.demo_ids import demo_id
from ar_domain.durable.flush import flush_store, schedule_flush
from ar_domain.durable.hydrate import hydrate_tenant
from ar_domain.durable.tracking import BUCKETS, TrackedDict, install_tracking

if TYPE_CHECKING:
    from typing import Any

_log = get_logger(__name__)


class SchemaNotReadyError(Exception):
    """Postgres answered, but the tenant tables are not migrated yet."""


_EMAIL_KEYS = {
    "admin@dev.local": "admin",
    "builder@dev.local": "builder",
    "member@dev.local": "member",
    "approver@dev.local": "approver",
}


@dataclass(frozen=True, slots=True)
class DevBinding:
    """Database ids for the dev tenant. Sessions use these when the API is durable."""

    tenant_id: uuid.UUID
    users: dict[str, uuid.UUID]


def should_bind() -> bool:
    """Skip Postgres during unit tests unless a test asks for it."""
    mode = os.environ.get("AR_DURABLE_STATE", "").strip().lower()
    if mode == "memory":
        return False
    if mode == "postgres":
        return True
    return "pytest" not in sys.modules


async def bind_store(store: object, database_url: str) -> DevBinding | None:
    """Hydrate and flush when Postgres answers. Return None when it does not."""
    engine = await _connect(platform_database_url(database_url))
    if engine is None:
        return None
    found = await _lookup(engine)
    if found is None:
        await engine.dispose()
        _log.info("durable_waiting_for_seed")
        return None
    tenant_id, users = found
    _remap(store, _id_map(tenant_id, users))
    await _remap_agents(store, engine, tenant_id)
    await _remap_catalogues(store, engine, tenant_id)
    install_tracking(store)
    store.durable_engine = engine  # type: ignore[attr-defined]
    store.durable = True  # type: ignore[attr-defined]
    store.flush_soon = lambda: schedule_flush(store)  # type: ignore[attr-defined]
    seeded = {name: set(getattr(store, name, {})) for name in BUCKETS}
    loaded: dict[str, set[object]] = {}
    store._initial_loaded = loaded  # type: ignore[attr-defined]
    try:
        await hydrate_tenant(store, engine, tenant_id)
    finally:
        store._initial_loaded = None  # type: ignore[attr-defined]
    for name, keys in seeded.items():
        bucket = getattr(store, name, None)
        if isinstance(bucket, TrackedDict):
            bucket.dirty.update(keys - loaded.get(name, set()))
    await flush_store(store)
    binding = DevBinding(tenant_id=tenant_id, users=users)
    store.dev_binding = binding  # type: ignore[attr-defined]
    _log.info("durable_bound", tenant_id=str(tenant_id))
    return binding


async def _connect(url: str) -> AsyncEngine | None:
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"timeout": 0.4, "statement_cache_size": 0},
    )
    try:
        async with asyncio.timeout(0.6):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — no database means the memory cache stays
        _log.info("durable_unavailable", error=type(exc).__name__)
        await engine.dispose()
        return None
    return engine


async def _lookup(engine: AsyncEngine) -> tuple[uuid.UUID, dict[str, uuid.UUID]] | None:
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            tenant = await session.scalar(text("SELECT id FROM tenants WHERE slug = 'dev'"))
            if not isinstance(tenant, uuid.UUID):
                return None
            result = await session.execute(
                text("SELECT id, email FROM users WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant},
            )
            users = {str(email).lower(): user_id for user_id, email in result}
    except Exception as exc:
        if _missing_relation(exc):
            raise SchemaNotReadyError() from exc
        raise
    if not users:
        return None
    return tenant, users


def _missing_relation(exc: BaseException) -> bool:
    current: BaseException | None = exc
    for _ in range(6):
        if current is None:
            return False
        sqlstate = getattr(current, "sqlstate", None)
        if sqlstate is None:
            sqlstate = getattr(getattr(current, "orig", None), "sqlstate", None)
        if sqlstate == "42P01" or type(current).__name__ == "UndefinedTableError":
            return True
        current = current.__cause__
    return False


def _id_map(tenant_id: uuid.UUID, users: dict[str, uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    mapping = {demo_id("tenant"): tenant_id}
    for email, key in _EMAIL_KEYS.items():
        user_id = users.get(email)
        if user_id is not None:
            mapping[demo_id(key)] = user_id
    return {left: right for left, right in mapping.items() if left != right}


def _remap(store: object, mapping: dict[uuid.UUID, uuid.UUID]) -> None:
    if not mapping:
        return
    for name in BUCKETS:
        current = getattr(store, name, None)
        if isinstance(current, dict):
            setattr(store, name, _remap_dict(current, mapping))


def _remap_dict(
    current: dict[object, object], mapping: dict[uuid.UUID, uuid.UUID]
) -> dict[object, object]:
    rebuilt: dict[object, object] = {}
    for key, value in current.items():
        new_key = mapping.get(key, key) if isinstance(key, uuid.UUID) else key
        rebuilt[new_key] = _remap_value(value, mapping)
    return rebuilt


def _remap_value(value: object, mapping: dict[uuid.UUID, uuid.UUID]) -> object:
    if isinstance(value, uuid.UUID):
        return mapping.get(value, value)
    if isinstance(value, dict):
        return {str(key): _remap_value(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_remap_value(item, mapping) for item in value]
    return value


async def _remap_agents(store: object, engine: AsyncEngine, tenant_id: uuid.UUID) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            text("SELECT id, slug, published_version_id FROM agents WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        by_slug = {str(slug): (agent_id, version_id) for agent_id, slug, version_id in result}
    agents = getattr(store, "agents", None)
    if not isinstance(agents, dict):
        return
    mapping: dict[uuid.UUID, uuid.UUID] = {}
    for agent in agents.values():
        if not isinstance(agent, dict):
            continue
        found = by_slug.get(str(agent.get("slug")))
        if found is None:
            continue
        agent_id = agent.get("id")
        if isinstance(agent_id, uuid.UUID) and agent_id != found[0]:
            mapping[agent_id] = found[0]
        published = agent.get("published_version_id")
        if isinstance(published, uuid.UUID) and found[1] is not None and published != found[1]:
            mapping[published] = found[1]
    _remap(store, mapping)


async def _remap_catalogues(store: object, engine: AsyncEngine, tenant_id: uuid.UUID) -> None:
    """Match demo catalogue rows by their database uniqueness keys before inserting."""
    catalogues = (
        ("skills", "skills", ("slug",)),
        ("skill_versions", "skill_versions", ("skill_id", "version")),
        ("knowledge_collections", "knowledge_collections", ("slug",)),
        ("knowledge_sources", "knowledge_sources", ("collection_id", "name")),
        ("knowledge_documents", "documents", ("source_id", "external_id")),
        ("document_chunks", "document_chunks", ("document_id", "ordinal", "index_version")),
        ("channel_integrations", "channel_integrations", ("kind", "name")),
        ("channel_identities", "channel_identities", ("integration_id", "external_user_id")),
        (
            "channel_threads",
            "channel_threads",
            ("integration_id", "external_channel_id", "external_thread_id"),
        ),
    )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        for bucket_name, table, keys in catalogues:
            result = await session.execute(
                text(f"SELECT * FROM {table} WHERE tenant_id = :tenant_id"),  # noqa: S608 - fixed table catalogue
                {"tenant_id": tenant_id},
            )
            existing = {
                tuple(row.get(key) for key in keys): row["id"]
                for row in result.mappings()
                if all(row.get(key) is not None for key in keys)
            }
            bucket = getattr(store, bucket_name, {})
            mapping = {}
            for row in bucket.values():
                identity = tuple(row.get(key) for key in keys)
                found = existing.get(identity)
                if found is not None and row.get("id") != found:
                    mapping[row["id"]] = found
            _remap(store, mapping)


def user_for_email(binding: DevBinding | None, email: str) -> uuid.UUID | None:
    """Database user id for a dev email, when the API is bound."""
    if binding is None:
        return None
    return binding.users.get(email.lower())


def binding_from(store: Any) -> DevBinding | None:
    found = getattr(store, "dev_binding", None)
    return found if isinstance(found, DevBinding) else None

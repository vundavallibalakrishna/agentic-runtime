"""Attach a process cache to Postgres when the database is up."""

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from ar_common.logging import get_logger
from ar_common.settings import get_settings
from ar_domain.db.engine import platform_database_url
from ar_domain.db.registry import import_models
from ar_domain.durable.flush import flush_store, schedule_flush
from ar_domain.durable.hydrate import hydrate_tenant
from ar_domain.durable.tracking import BUCKETS, TrackedDict, install_tracking

if TYPE_CHECKING:
    import uuid
    from typing import Any

_log = get_logger(__name__)


class SchemaNotReadyError(Exception):
    """Postgres answered, but the tenant tables are not migrated yet."""


class TenantNotReadyError(Exception):
    """The schema is there, but the tenant this process serves is not in it yet."""


@dataclass(frozen=True, slots=True)
class TenantBinding:
    """The tenant a process serves, read from the database when it attaches."""

    tenant_id: uuid.UUID
    slug: str
    name: str
    plan: str
    users: dict[str, uuid.UUID]


def should_bind() -> bool:
    """Skip Postgres during unit tests unless a test asks for it."""
    mode = os.environ.get("AR_DURABLE_STATE", "").strip().lower()
    if mode == "memory":
        return False
    if mode == "postgres":
        return True
    return "pytest" not in sys.modules


async def bind_store(
    store: object, database_url: str, *, tenant_slug: str | None = None
) -> TenantBinding | None:
    """Attach the store to its tenant's rows. Return None when Postgres does not answer.

    The tenant is read from the ``tenants`` table: the one named by ``tenant_slug`` (by
    default ``AR_BOOTSTRAP_TENANT_SLUG``), or the only tenant when no slug is set. Nothing
    about the tenant or its people is taken from code.
    """
    # Every process that writes through this store needs the whole schema registered.
    import_models()
    engine = await _connect(platform_database_url(database_url))
    if engine is None:
        return None
    slug = get_settings().bootstrap_tenant_slug if tenant_slug is None else tenant_slug
    try:
        binding = await _lookup(engine, slug.strip())
    except BaseException:
        await engine.dispose()
        raise
    install_tracking(store)
    store.durable_engine = engine  # type: ignore[attr-defined]
    store.durable = True  # type: ignore[attr-defined]
    store.flush_soon = lambda: schedule_flush(store)  # type: ignore[attr-defined]
    seeded = {name: set(getattr(store, name, {})) for name in BUCKETS}
    loaded: dict[str, set[object]] = {}
    store._initial_loaded = loaded  # type: ignore[attr-defined]
    try:
        await hydrate_tenant(store, engine, binding.tenant_id)
    finally:
        store._initial_loaded = None  # type: ignore[attr-defined]
    from ar_domain.orchestration.reconcile import reconcile_interrupted  # noqa: PLC0415

    reconcile_interrupted(store)
    # Platform rows built in this process (the built-in tool catalogue) that the database
    # does not hold yet are written once.
    for name, keys in seeded.items():
        bucket = getattr(store, name, None)
        if isinstance(bucket, TrackedDict):
            bucket.dirty.update(keys - loaded.get(name, set()))
    await flush_store(store)
    store.tenant_binding = binding  # type: ignore[attr-defined]
    _log.info("durable_bound", tenant_id=str(binding.tenant_id), tenant=binding.slug)
    return binding


async def attach_store(store: object, database_url: str, *, retry_s: float = 2.0) -> TenantBinding:
    """Attach a worker's store, waiting until the database is up and names its tenant.

    A worker can do nothing without its tenant, so it waits for the database, for the
    schema and for the seed, in any environment.
    """
    while True:
        waiting_for = "database"
        try:
            binding = await bind_store(store, database_url)
        except SchemaNotReadyError:
            binding, waiting_for = None, "schema"
        except TenantNotReadyError:
            binding, waiting_for = None, "tenant"
        if binding is not None:
            return binding
        _log.info("durable_waiting", waiting_for=waiting_for)
        await asyncio.sleep(retry_s)


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


async def _lookup(engine: AsyncEngine, slug: str) -> TenantBinding:
    """Find the tenant to serve, or raise when the database does not name one yet."""
    try:
        found, users = await _tenant_rows(engine, slug)
    except Exception as exc:
        if _missing_relation(exc):
            raise SchemaNotReadyError from exc
        raise
    if len(found) != 1:
        _log.info("durable_tenant_not_ready", tenants=len(found), slug=slug or None)
        raise TenantNotReadyError
    tenant_id, tenant_slug, name, plan = found[0]
    return TenantBinding(
        tenant_id=tenant_id, slug=str(tenant_slug), name=str(name), plan=str(plan), users=users
    )


async def _tenant_rows(
    engine: AsyncEngine, slug: str
) -> tuple[list[tuple[uuid.UUID, str, str, str]], dict[str, uuid.UUID]]:
    """Up to two matching tenants, and the people of the first."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        result = await session.execute(
            text(
                "SELECT t.id, t.slug, t.name, p.key FROM tenants t "
                "JOIN plans p ON p.id = t.plan_id "
                "WHERE t.deleted_at IS NULL AND (:slug = '' OR t.slug = :slug) "
                "ORDER BY t.created_at LIMIT 2"
            ),
            {"slug": slug},
        )
        found = [(row[0], str(row[1]), str(row[2]), str(row[3])) for row in result]
        if len(found) != 1:
            return found, {}
        people = await session.execute(
            text("SELECT id, email FROM users WHERE tenant_id = :tenant_id"),
            {"tenant_id": found[0][0]},
        )
        return found, {str(email).lower(): user_id for user_id, email in people}


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


def user_for_email(binding: TenantBinding | None, email: str) -> uuid.UUID | None:
    """Database user id for an address, when the process is attached to a tenant."""
    if binding is None:
        return None
    return binding.users.get(email.lower())


def binding_from(store: Any) -> TenantBinding | None:
    found = getattr(store, "tenant_binding", None)
    return found if isinstance(found, TenantBinding) else None

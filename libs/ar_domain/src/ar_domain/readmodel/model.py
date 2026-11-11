"""Postgres is the API read model. Nothing tenant-owned is kept on the process."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ar_domain.db.engine import platform_database_url
from ar_domain.db.registry import import_models
from ar_domain.durable.tracking import BUCKETS, TrackedDict

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

_CONFIG = (
    "allow_loopback",
    "scanner",
    "fake_models_allowed",
    "event_bus",
    "shared_idempotency",
    "temporal_required",
    "temporal_client",
    "temporal_up",
    "model_gateway_url",
    "opa_url",
    "opa_timeout_ms",
    "tool_gateway_http",
    "pack_signature_required",
    "pack_trusted_keys",
    "sandbox_launcher",
    "pod_creator",
    "sse_gate",
)

# Tables a payload may name. The SQL is fixed; the key is not interpolated.
_TENANT_SQL = {
    "runs": "SELECT tenant_id FROM runs WHERE id = :id",
    "routines": "SELECT tenant_id FROM routines WHERE id = :id",
    "routine_events": "SELECT tenant_id FROM routine_events WHERE id = :id",
    "approvals": "SELECT tenant_id FROM approvals WHERE id = :id",
    "documents": "SELECT tenant_id FROM documents WHERE id = :id",
    "knowledge_sources": "SELECT tenant_id FROM knowledge_sources WHERE id = :id",
    "knowledge_collections": "SELECT tenant_id FROM knowledge_collections WHERE id = :id",
    "agent_versions": "SELECT tenant_id FROM agent_versions WHERE id = :id",
    "users": "SELECT tenant_id FROM users WHERE id = :id",
    "eval_runs": "SELECT tenant_id FROM eval_runs WHERE id = :id",
    "sandboxes": "SELECT tenant_id FROM sandboxes WHERE id = :id",
}


class RepositoryReadModel:
    """Process handle for the read model. Tenant rows live in Postgres.

    Each request or activity opens a ``RequestUnit``, loads that tenant, and
    commits the unit in one transaction. The unit is then discarded.
    """

    def __init__(self, *, database_url: str, **options: Any) -> None:
        self.database_url = database_url
        self.engine: AsyncEngine | None = None
        self.allow_loopback = bool(options.get("allow_loopback", False))
        self.scanner = str(options.get("scanner", "none"))
        self.fake_models_allowed = bool(options.get("fake_models_allowed", False))
        self.event_bus: object | None = None
        self.shared_idempotency: object | None = None
        self.temporal_required = False
        self.temporal_client: object | None = None
        self.temporal_up = False
        self.model_gateway_url = ""
        self.opa_url = ""
        self.opa_timeout_ms = 200
        self.tool_gateway_http = False
        self.pack_signature_required = False
        self.pack_trusted_keys: dict[str, str] = {}
        self.sandbox_launcher: object | None = None
        self.pod_creator: object | None = None
        self.sse_gate: object | None = None
        self._bind_attempted = False
        self._ingest_worker = False

    @classmethod
    def from_settings(cls, settings: object, **options: Any) -> RepositoryReadModel:
        url = str(getattr(settings, "database_url", "") or "")
        model = cls(database_url=url, **options)
        model.model_gateway_url = str(getattr(settings, "model_gateway_url", "") or "")
        model.temporal_required = bool(getattr(settings, "temporal_required", False))
        return model

    def holds_tenant_state(self) -> bool:
        """False. Tenant buckets are not attributes of this object."""
        return any(isinstance(getattr(self, name, None), dict) for name in BUCKETS)

    async def engine_for(self) -> AsyncEngine:
        """The platform engine flush already uses. Tenant context is set per transaction."""
        if isinstance(self.engine, AsyncEngine):
            return self.engine
        import_models()
        from ar_domain.durable.bind import _connect  # noqa: PLC0415

        engine = await _connect(platform_database_url(self.database_url))
        if engine is None:
            from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

            engine = create_async_engine(
                platform_database_url(self.database_url),
                pool_pre_ping=True,
                hide_parameters=True,
                connect_args={"statement_cache_size": 0},
            )
        self.engine = engine
        return engine

    async def wait_ready(self, *, retry_s: float = 2.0) -> None:
        """Wait until Postgres has the schema and a tenant. Do not hydrate one."""
        from ar_common.settings import get_settings  # noqa: PLC0415
        from ar_domain.durable.bind import (  # noqa: PLC0415
            SchemaNotReadyError,
            TenantNotReadyError,
            _lookup,
        )

        slug = get_settings().bootstrap_tenant_slug
        while True:
            try:
                engine = await self.engine_for()
                await _lookup(engine, slug.strip())
            except SchemaNotReadyError, TenantNotReadyError, OSError, ConnectionError:
                self.engine = None
                await asyncio.sleep(retry_s)
                continue
            except Exception as exc:  # noqa: BLE001 - a down database retries
                from ar_common.logging import get_logger  # noqa: PLC0415

                get_logger(__name__).info("read_model_waiting", error=type(exc).__name__)
                self.engine = None
                await asyncio.sleep(retry_s)
                continue
            return

    async def tenant_ids(self) -> list[uuid.UUID]:
        """Active tenants. Sweeps that have no payload walk this list."""
        engine = await self.engine_for()
        async with engine.connect() as connection:
            rows = (
                await connection.execute(text("SELECT id FROM tenants WHERE status = 'active'"))
            ).all()
        return [row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0])) for row in rows]

    async def lookup_tenant(self, slug: str) -> Any:
        """The tenant row for sign-in. It is not cached on the process."""
        from ar_domain.durable.bind import TenantBinding, _lookup  # noqa: PLC0415

        engine = await self.engine_for()
        found = await _lookup(engine, slug.strip())
        if not isinstance(found, TenantBinding):
            raise TypeError("tenant lookup did not return a binding")
        return found

    async def resolve_tenant(self, payload: object) -> uuid.UUID | None:
        """The tenant an activity payload names, read from Postgres."""
        named = _direct_tenant(payload)
        if named is not None:
            return named
        if isinstance(payload, str):
            found = _as_uuid(payload)
            if found is None:
                return None
            return await self._tenant_of("approvals", found)
        if not isinstance(payload, dict):
            return None
        for key, table in (
            ("run_id", "runs"),
            ("routine_id", "routines"),
            ("event_id", "routine_events"),
            ("approval_id", "approvals"),
            ("document_id", "documents"),
            ("source_id", "knowledge_sources"),
            ("collection_id", "knowledge_collections"),
            ("agent_version_id", "agent_versions"),
            ("user_id", "users"),
            ("eval_run_id", "eval_runs"),
            ("sandbox_id", "sandboxes"),
        ):
            found = _as_uuid(payload.get(key))
            if found is None:
                continue
            tenant = await self._tenant_of(table, found)
            if tenant is not None:
                return tenant
        return None

    async def _tenant_of(self, table: str, row_id: uuid.UUID) -> uuid.UUID | None:
        statement = _TENANT_SQL.get(table)
        if statement is None:
            return None
        engine = await self.engine_for()
        try:
            async with engine.connect() as connection:
                row = (await connection.execute(text(statement), {"id": row_id})).first()
        except Exception:  # noqa: BLE001 - a missing table is not a tenant
            return None
        if row is None or row[0] is None:
            return None
        return row[0] if isinstance(row[0], uuid.UUID) else uuid.UUID(str(row[0]))

    @asynccontextmanager
    async def open(
        self,
        tenant_id: uuid.UUID,
        *,
        user_id: str = "",
        request_id: str = "",
    ) -> AsyncIterator[Any]:
        """Load one tenant, yield the unit, commit it, then drop it."""
        unit = self._new_unit()
        unit.context_tenant_id = tenant_id
        unit.context_user_id = user_id
        unit.context_request_id = request_id
        engine = await self.engine_for()
        unit.durable_engine = engine
        unit.durable = True
        await _load(unit, engine, tenant_id)
        try:
            yield unit
        finally:
            from ar_domain.durable.flush import flush_store  # noqa: PLC0415

            await flush_store(unit)

    def _new_unit(self) -> Any:
        from ar_domain.chat.service import RequestUnit  # noqa: PLC0415

        unit = RequestUnit(
            allow_loopback=self.allow_loopback,
            scanner=self.scanner,
            fake_models_allowed=self.fake_models_allowed,
        )
        for name in _CONFIG:
            if hasattr(self, name):
                setattr(unit, name, getattr(self, name))
        from ar_domain.process_state import bind_unit  # noqa: PLC0415

        bind_unit(self, unit)
        return unit


def _direct_tenant(payload: object) -> uuid.UUID | None:
    if not isinstance(payload, dict):
        return None
    return _as_uuid(payload.get("tenant_id"))


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


async def _load(unit: object, engine: AsyncEngine, tenant_id: uuid.UUID) -> None:
    """Hydrate inside a short read transaction. The commit transaction is the flush."""
    from ar_domain.durable.hydrate import hydrate_tenant  # noqa: PLC0415
    from ar_domain.durable.tracking import install_tracking  # noqa: PLC0415

    install_tracking(unit)
    seeded = {name: set(getattr(unit, name, {})) for name in BUCKETS}
    loaded: dict[str, set[object]] = {}
    unit._initial_loaded = loaded  # type: ignore[attr-defined]
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply_tenant_context(session, tenant_id)
        try:
            await hydrate_tenant(unit, engine, tenant_id, session=session)
        finally:
            unit._initial_loaded = None  # type: ignore[attr-defined]
    for name, keys in seeded.items():
        bucket = getattr(unit, name, None)
        if isinstance(bucket, TrackedDict):
            bucket.dirty.update(keys - loaded.get(name, set()))


async def apply_tenant_context(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    user_id: str = "",
    request_id: str = "",
) -> None:
    """Set the transaction-local tenant context the repositories run under."""
    await session.execute(
        text(
            "SELECT set_config('app.tenant_id', :tenant_id, true), "
            "set_config('app.user_id', :user_id, true), "
            "set_config('app.request_id', :request_id, true)"
        ),
        {
            "tenant_id": str(tenant_id),
            "user_id": user_id,
            "request_id": request_id,
        },
    )

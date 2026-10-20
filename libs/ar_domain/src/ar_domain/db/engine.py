"""Async engines and dedicated-tenant routing.

Spec: docs/04-data/rls.md §6, docs/07-ops/scaling.md (pool of 20 via PgBouncer).
"""

import uuid  # noqa: TC003
from typing import Any  # noqa: TC003

import orjson
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ar_common.settings import get_settings

# PgBouncer transaction pooling: asyncpg must not cache prepared statements.
_CONNECT_ARGS: dict[str, Any] = {"statement_cache_size": 0}
_POOL_SIZE = 20
_MAX_OVERFLOW = 10
_engines: dict[str, AsyncEngine] = {}


def swap_user(url: str, username: str, password: str) -> str:
    """Return ``url`` with the user and password replaced. The driver is kept."""
    parsed = make_url(url)
    return parsed.set(username=username, password=password).render_as_string(hide_password=False)


def app_database_url() -> str:
    """Service DSN. Running services connect as ``ar_app``."""
    return get_settings().database_url


def platform_database_url(url: str | None = None) -> str:
    """DSN for ``ar_platform`` (BYPASSRLS). Dev passwords match the role name."""
    current = app_database_url() if url is None else url
    parsed = make_url(current)
    if parsed.username == "ar_platform":
        return current
    return swap_user(current, "ar_platform", "ar_platform")


def owner_database_url(url: str | None = None) -> str:
    """DSN for migrations and seed. ``ar_app`` URLs are rewritten to ``ar_owner``."""
    current = app_database_url() if url is None else url
    parsed = make_url(current)
    if parsed.username in {"ar_owner", "postgres", "test"}:
        return current
    if parsed.username == "ar_app":
        return swap_user(current, "ar_owner", "ar_owner")
    return current


def tenant_routes() -> dict[str, str]:
    """Parse ``AR_TENANT_DB_ROUTES`` (JSON object of tenant id to DSN)."""
    raw = getattr(get_settings(), "tenant_db_routes", None)
    text = _env_routes() if not isinstance(raw, str) or raw.strip() in {"", "{}"} else raw
    if text.strip() in {"", "{}"}:
        return {}
    parsed = orjson.loads(text)
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _env_routes() -> str:
    import os  # noqa: PLC0415

    return os.environ.get("AR_TENANT_DB_ROUTES", "{}")


def get_engine(url: str) -> AsyncEngine:
    """Return a cached async engine for ``url``."""
    existing = _engines.get(url)
    if existing is not None:
        return existing
    engine = create_async_engine(
        url,
        pool_size=_POOL_SIZE,
        max_overflow=_MAX_OVERFLOW,
        pool_timeout=30,
        pool_pre_ping=True,
        connect_args=_CONNECT_ARGS,
    )
    _engines[url] = engine
    return engine


def engine_for(tenant_id: uuid.UUID) -> AsyncEngine:
    """Route a tenant to its dedicated database, or the shared app database."""
    dedicated = tenant_routes().get(str(tenant_id))
    if dedicated:
        return get_engine(dedicated)
    return get_engine(app_database_url())


def platform_engine() -> AsyncEngine:
    """Engine used by ``platform_session``."""
    return get_engine(platform_database_url())


def dispose_engines() -> None:
    """Drop cached engines. Tests call this after changing settings."""
    _engines.clear()

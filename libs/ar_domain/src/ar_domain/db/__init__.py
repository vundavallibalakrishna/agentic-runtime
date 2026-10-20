"""Database access. Spec: docs/04-data/rls.md."""

from ar_domain.db.base import Base, metadata
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.engine import (
    app_database_url,
    dispose_engines,
    engine_for,
    get_engine,
    owner_database_url,
    platform_database_url,
    platform_engine,
    swap_user,
    tenant_routes,
)
from ar_domain.db.repository import BaseRepository
from ar_domain.db.session import platform_session, register_platform_audit_hook, tenant_session

__all__ = [
    "Base",
    "BaseRepository",
    "Principal",
    "TenantContext",
    "app_database_url",
    "dispose_engines",
    "engine_for",
    "get_engine",
    "metadata",
    "owner_database_url",
    "platform_database_url",
    "platform_engine",
    "platform_session",
    "register_platform_audit_hook",
    "swap_user",
    "tenant_routes",
    "tenant_session",
]

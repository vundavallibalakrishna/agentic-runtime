"""Tenant and platform transactions. Spec: docs/04-data/rls.md §2."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ar_domain.db.engine import engine_for, platform_engine

if TYPE_CHECKING:
    from ar_domain.db.context import TenantContext

PlatformHook = Callable[[AsyncSession, str], Awaitable[None]]


class _Hook:
    current: PlatformHook | None = None


def register_platform_audit_hook(hook: PlatformHook) -> None:
    """Install the audit writer used by ``platform_session`` (M1-T05)."""
    _Hook.current = hook


def platform_audit_hook() -> PlatformHook | None:
    return _Hook.current


@asynccontextmanager
async def tenant_session(
    ctx: TenantContext,
    *,
    engine: AsyncEngine | None = None,
) -> AsyncIterator[AsyncSession]:
    """Open a transaction and set ``app.tenant_id``, ``app.user_id``, ``app.request_id``.

    Settings are transaction-local (``set_config`` third argument ``true``) so a
    PgBouncer transaction-pooled connection cannot leak them.
    """
    bind = engine_for(ctx.tenant_id) if engine is None else engine
    async with AsyncSession(bind, expire_on_commit=False) as session, session.begin():
        await session.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant_id, true), "
                "set_config('app.user_id', :user_id, true), "
                "set_config('app.request_id', :request_id, true)"
            ),
            {
                "tenant_id": str(ctx.tenant_id),
                "user_id": "" if ctx.user_id is None else str(ctx.user_id),
                "request_id": ctx.request_id,
            },
        )
        yield session


@asynccontextmanager
async def platform_session(
    reason: str,
    *,
    engine: AsyncEngine | None = None,
) -> AsyncIterator[AsyncSession]:
    """Open a BYPASSRLS transaction and record why it was opened."""
    bind = platform_engine() if engine is None else engine
    async with AsyncSession(bind, expire_on_commit=False) as session, session.begin():
        hook = _Hook.current
        if hook is not None:
            await hook(session, reason)
        yield session

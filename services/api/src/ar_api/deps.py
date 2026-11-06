"""Request dependencies. Spec: docs/03-specs/01-api-bff.md §4."""

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, TypeVar

from fastapi import Depends, Request

from ar_common.errors import ForbiddenError, UnauthenticatedError
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import platform_session, tenant_session
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.service import IdentityService, IdentityStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from sqlalchemy.ext.asyncio import AsyncEngine

Route = TypeVar("Route", bound="Callable[..., object]")

PUBLIC = "public"
AUTHENTICATED = "authenticated"


def expose(*, permission: str | None, public: bool) -> Callable[[Route], Route]:
    """Mark a route for the permission lint."""

    def decorate(func: Route) -> Route:
        func.__public__ = public  # type: ignore[attr-defined]
        func.__permission__ = permission  # type: ignore[attr-defined]
        func.__authenticated__ = not public  # type: ignore[attr-defined]
        return func

    return decorate


def current_principal(request: Request) -> Principal:
    """Return the principal set by the authenticate middleware."""
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise UnauthenticatedError()
    return principal


def require_permission(permission: str) -> Callable[..., object]:
    """Dependency that enforces one permission, including team scope."""

    async def dependency(request: Request) -> Principal:
        principal = current_principal(request)
        team_raw = request.query_params.get("team_id")
        team_id = uuid.UUID(team_raw) if team_raw else None
        if not principal.allows(permission, team_id=team_id):
            raise ForbiddenError(f"missing permission {permission}")
        return principal

    return dependency


@asynccontextmanager
async def identity_store(
    request: Request, ctx: TenantContext, *, engine: AsyncEngine | None = None
) -> AsyncIterator[IdentityStore]:
    """One tenant's identity rows inside one transaction.

    The rows come from the database. ``app.state.identity_provider`` is a seam that the
    application leaves empty; test setup fills it to read identity from memory.
    """
    provider = getattr(request.app.state, "identity_provider", None)
    if provider is not None:
        yield provider(ctx)
        return
    async with tenant_session(ctx, engine=engine) as session:
        yield IdentityRepository(session, ctx)


async def get_identity(request: Request) -> AsyncIterator[IdentityService]:
    """Open a tenant transaction and yield the identity service."""
    override = getattr(request.app.state, "identity_override", None)
    if override is not None:
        yield override
        return
    principal = current_principal(request)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with identity_store(request, ctx) as store:
        yield IdentityService(store)


IdentityDep = Annotated[IdentityService, Depends(get_identity)]
PrincipalDep = Annotated[Principal, Depends(current_principal)]


async def get_tenant_writer(request: Request) -> AsyncIterator[IdentityService]:
    """Global tenant rows require the audited platform transaction (RLS §3.4)."""
    override = getattr(request.app.state, "identity_override", None)
    if override is not None:
        yield override
        return
    principal = current_principal(request)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    provider = getattr(request.app.state, "identity_provider", None)
    if provider is not None:
        yield IdentityService(provider(ctx))
        return
    async with platform_session(f"tenant settings update: {ctx.tenant_id}") as session:
        yield IdentityService(IdentityRepository(session, ctx))


TenantWriterDep = Annotated[IdentityService, Depends(get_tenant_writer)]

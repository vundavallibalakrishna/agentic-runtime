"""Request dependencies. Spec: docs/03-specs/01-api-bff.md §4."""

import uuid
from typing import TYPE_CHECKING, Annotated, TypeVar

from fastapi import Depends, Request

from ar_common.errors import ForbiddenError, UnauthenticatedError
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import platform_session, tenant_session
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.service import IdentityService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

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


async def get_identity(request: Request) -> AsyncIterator[IdentityService]:
    """Open a tenant transaction and yield the identity service."""
    override = getattr(request.app.state, "identity_override", None)
    if override is not None:
        yield override
        return
    principal = current_principal(request)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    chat = getattr(request.app.state, "chat", None)
    if chat is not None:
        from ar_api.auth.memory_identity import memory_identity, use_memory_identity  # noqa: PLC0415

        if use_memory_identity(chat):
            yield memory_identity(chat, ctx)
            return
    async with tenant_session(ctx) as session:
        yield IdentityService(IdentityRepository(session, ctx))


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
    chat = getattr(request.app.state, "chat", None)
    if chat is not None:
        from ar_api.auth.memory_identity import memory_identity, use_memory_identity  # noqa: PLC0415

        if use_memory_identity(chat):
            yield memory_identity(chat, ctx)
            return
    async with platform_session(f"tenant settings update: {ctx.tenant_id}") as session:
        yield IdentityService(IdentityRepository(session, ctx))


TenantWriterDep = Annotated[IdentityService, Depends(get_tenant_writer)]

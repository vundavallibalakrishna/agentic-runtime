"""Request dependencies. Spec: docs/03-specs/01-api-bff.md §4."""

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from ar_common.errors import ForbiddenError, UnauthenticatedError
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.service import IdentityService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

PUBLIC = "public"
AUTHENTICATED = "authenticated"


def expose(
    *, permission: str | None, public: bool
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Mark a route for the permission lint."""

    def decorate(func: Callable[..., object]) -> Callable[..., object]:
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
    async with tenant_session(ctx) as session:
        yield IdentityService(IdentityRepository(session, ctx))


IdentityDep = Annotated[IdentityService, Depends(get_identity)]
PrincipalDep = Annotated[Principal, Depends(current_principal)]

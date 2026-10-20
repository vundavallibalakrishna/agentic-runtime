"""Current user. Spec: docs/03-specs/02-identity-tenancy.md §3.3."""

from typing import TYPE_CHECKING

from fastapi import APIRouter

from ar_api.deps import IdentityDep, PrincipalDep, expose
from ar_contracts.api_model import ApiModel
from ar_contracts.identity import Me

if TYPE_CHECKING:
    from ar_domain.db.context import Principal
    from ar_domain.identity.models import User

router = APIRouter()


class MePatch(ApiModel):
    display_name: str | None = None
    settings: dict[str, object] | None = None


def _me(user: User, principal: Principal) -> Me:
    settings = user.settings if isinstance(user.settings, dict) else {}
    return Me(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
        settings=settings,
    )


@router.get("/api/v1/me", response_model=Me)
@expose(public=False, permission=None)
async def get_me(principal: PrincipalDep, identity: IdentityDep) -> Me:
    return _me(await identity.current_user(), principal)


@router.patch("/api/v1/me", response_model=Me)
@expose(public=False, permission=None)
async def patch_me(body: MePatch, principal: PrincipalDep, identity: IdentityDep) -> Me:
    user = await identity.update_me(display_name=body.display_name, settings=body.settings)
    return _me(user, principal)

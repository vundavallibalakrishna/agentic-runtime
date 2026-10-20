"""Current user. Spec: docs/03-specs/02-identity-tenancy.md §3.3."""

from fastapi import APIRouter

from ar_api.deps import IdentityDep, PrincipalDep, expose
from ar_contracts.json_api import ApiModel

router = APIRouter()


class MePatch(ApiModel):
    display_name: str | None = None
    settings: dict[str, object] | None = None


@router.get("/api/v1/me")
@expose(public=False, permission=None)
async def get_me(principal: PrincipalDep, identity: IdentityDep) -> dict[str, object]:
    _ = identity.ctx
    return {
        "id": principal.id,
        "email": principal.email,
        "display_name": principal.display_name,
        "roles": sorted(principal.roles),
        "permissions": sorted(principal.permissions),
        "teams": [],
        "groups": [],
        "settings": {},
    }


@router.patch("/api/v1/me")
@expose(public=False, permission=None)
async def patch_me(body: MePatch, identity: IdentityDep) -> dict[str, object]:
    user = await identity.update_me(display_name=body.display_name, settings=body.settings)
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "settings": user.settings,
    }

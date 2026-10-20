"""Teams. Spec: docs/03-specs/02-identity-tenancy.md §3.6."""

import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.json_api import ApiModel

router = APIRouter()


class TeamCreate(ApiModel):
    slug: str
    name: str
    description: str = ""


class TeamMemberCreate(ApiModel):
    user_id: uuid.UUID
    team_role: str = "member"


def _team(row: object) -> dict[str, object]:
    return {"id": str(row.id), "slug": row.slug, "name": row.name, "description": row.description}  # type: ignore[attr-defined]


@router.get("/api/v1/teams", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def list_teams(identity: IdentityDep) -> dict[str, object]:
    return {"data": [_team(row) for row in await identity.store.list_teams()], "next_cursor": None}


@router.post("/api/v1/teams", dependencies=[Depends(require_permission("teams:manage"))])
@expose(public=False, permission="teams:manage")
async def create_team(body: TeamCreate, identity: IdentityDep) -> dict[str, object]:
    return _team(
        await identity.create_team(slug=body.slug, name=body.name, description=body.description)
    )


@router.get("/api/v1/teams/{team_id}", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def get_team(team_id: uuid.UUID, identity: IdentityDep) -> dict[str, object]:
    return _team(await identity._team(team_id))


@router.patch("/api/v1/teams/{team_id}", dependencies=[Depends(require_permission("teams:manage"))])
@expose(public=False, permission="teams:manage")
async def patch_team(
    team_id: uuid.UUID, body: TeamCreate, identity: IdentityDep
) -> dict[str, object]:
    team = await identity._team(team_id)
    team.name = body.name
    team.description = body.description
    return _team(team)


@router.delete(
    "/api/v1/teams/{team_id}", dependencies=[Depends(require_permission("teams:manage"))]
)
@expose(public=False, permission="teams:manage")
async def delete_team(team_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    await identity.delete_team(team_id)
    return {"deleted": True}


@router.post(
    "/api/v1/teams/{team_id}/members", dependencies=[Depends(require_permission("teams:manage"))]
)
@expose(public=False, permission="teams:manage")
async def add_member(
    team_id: uuid.UUID, body: TeamMemberCreate, identity: IdentityDep
) -> dict[str, bool]:
    await identity.add_team_member(team_id, body.user_id, body.team_role)
    return {"added": True}


@router.delete(
    "/api/v1/teams/{team_id}/members/{user_id}",
    dependencies=[Depends(require_permission("teams:manage"))],
)
@expose(public=False, permission="teams:manage")
async def remove_member(
    team_id: uuid.UUID, user_id: uuid.UUID, identity: IdentityDep
) -> dict[str, bool]:
    await identity._assert_team_manager(team_id)
    for member in await identity.store.team_members(team_id):
        if member.user_id == user_id:
            await identity.store.delete(member)
            return {"removed": True}
    from ar_common.errors import NotFoundError  # noqa: PLC0415

    raise NotFoundError("member not found")

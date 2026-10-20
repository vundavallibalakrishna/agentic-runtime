"""Groups. Spec: docs/03-specs/02-identity-tenancy.md §3.5."""

import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.api_model import ApiModel

router = APIRouter()


class GroupCreate(ApiModel):
    name: str


def _group(row: object) -> dict[str, object]:
    return {"id": str(row.id), "name": row.name, "source": row.source}  # type: ignore[attr-defined]


@router.get("/api/v1/groups", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def list_groups(identity: IdentityDep, source: str | None = None) -> dict[str, object]:
    rows = await identity.store.list_groups(source=source)
    return {"data": [_group(row) for row in rows], "next_cursor": None}


@router.post("/api/v1/groups", dependencies=[Depends(require_permission("users:manage"))])
@expose(public=False, permission="users:manage")
async def create_group(body: GroupCreate, identity: IdentityDep) -> dict[str, object]:
    return _group(await identity.create_group(body.name))


@router.delete(
    "/api/v1/groups/{group_id}", dependencies=[Depends(require_permission("users:manage"))]
)
@expose(public=False, permission="users:manage")
async def delete_group(group_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    await identity.delete_group(group_id)
    return {"deleted": True}


@router.get(
    "/api/v1/groups/{group_id}/members", dependencies=[Depends(require_permission("users:read"))]
)
@expose(public=False, permission="users:read")
async def list_members(group_id: uuid.UUID, identity: IdentityDep) -> dict[str, object]:
    await identity._group(group_id)
    return {"data": [str(item) for item in await identity.store.group_member_ids(group_id)]}


@router.put(
    "/api/v1/groups/{group_id}/members/{user_id}",
    dependencies=[Depends(require_permission("users:manage"))],
)
@expose(public=False, permission="users:manage")
async def put_member(
    group_id: uuid.UUID, user_id: uuid.UUID, identity: IdentityDep
) -> dict[str, bool]:
    await identity.add_group_member(group_id, user_id)
    return {"added": True}


@router.delete(
    "/api/v1/groups/{group_id}/members/{user_id}",
    dependencies=[Depends(require_permission("users:manage"))],
)
@expose(public=False, permission="users:manage")
async def delete_member(
    group_id: uuid.UUID, user_id: uuid.UUID, identity: IdentityDep
) -> dict[str, bool]:
    await identity.remove_group_member(group_id, user_id)
    return {"removed": True}

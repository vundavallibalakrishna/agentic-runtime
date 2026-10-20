"""Roles, assignments and the permission catalogue."""

import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.json_api import ApiModel
from ar_domain.identity.permissions import PERMISSIONS

router = APIRouter()


class RoleCreate(ApiModel):
    key: str
    name: str
    description: str = ""
    permissions: list[str]


class RolePatch(ApiModel):
    name: str | None = None
    permissions: list[str] | None = None


class AssignmentCreate(ApiModel):
    role_id: uuid.UUID
    principal_type: str
    principal_id: uuid.UUID
    scope_type: str = "tenant"
    scope_id: uuid.UUID | None = None


@router.get("/api/v1/permissions")
@expose(public=False, permission=None)
async def list_permissions() -> list[dict[str, str]]:
    return [
        {"key": item.key, "description": item.description, "category": item.category}
        for item in PERMISSIONS
    ]


@router.get("/api/v1/roles", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def list_roles(identity: IdentityDep) -> dict[str, object]:
    rows = await identity.store.list_roles()
    return {
        "data": [
            {
                "id": str(row.id),
                "key": row.key,
                "name": row.name,
                "permissions": list(row.permissions),
                "is_system": row.is_system,
            }
            for row in rows
        ]
    }


@router.post("/api/v1/roles", dependencies=[Depends(require_permission("roles:manage"))])
@expose(public=False, permission="roles:manage")
async def create_role(body: RoleCreate, identity: IdentityDep) -> dict[str, object]:
    row = await identity.create_role(
        key=body.key, name=body.name, description=body.description, permissions=body.permissions
    )
    return {"id": str(row.id), "key": row.key}


@router.patch("/api/v1/roles/{role_id}", dependencies=[Depends(require_permission("roles:manage"))])
@expose(public=False, permission="roles:manage")
async def patch_role(
    role_id: uuid.UUID, body: RolePatch, identity: IdentityDep
) -> dict[str, object]:
    row = await identity.update_role(role_id, name=body.name, permissions=body.permissions)
    return {"id": str(row.id), "key": row.key, "permissions": list(row.permissions)}


@router.delete(
    "/api/v1/roles/{role_id}", dependencies=[Depends(require_permission("roles:manage"))]
)
@expose(public=False, permission="roles:manage")
async def delete_role(role_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    await identity.delete_role(role_id)
    return {"deleted": True}


@router.get("/api/v1/role-assignments", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def list_assignments(identity: IdentityDep) -> dict[str, object]:
    rows = await identity.store.list_assignments()
    return {
        "data": [
            {
                "id": str(row.id),
                "role_id": str(row.role_id),
                "principal_type": row.principal_type,
                "principal_id": str(row.principal_id),
                "scope_type": row.scope_type,
            }
            for row in rows
        ]
    }


@router.post("/api/v1/role-assignments", dependencies=[Depends(require_permission("roles:manage"))])
@expose(public=False, permission="roles:manage")
async def create_assignment(body: AssignmentCreate, identity: IdentityDep) -> dict[str, str]:
    row = await identity.assign_role(
        role_id=body.role_id,
        principal_type=body.principal_type,
        principal_id=body.principal_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
    )
    return {"id": str(row.id)}


@router.delete(
    "/api/v1/role-assignments/{assignment_id}",
    dependencies=[Depends(require_permission("roles:manage"))],
)
@expose(public=False, permission="roles:manage")
async def delete_assignment(assignment_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    await identity.delete_assignment(assignment_id)
    return {"deleted": True}

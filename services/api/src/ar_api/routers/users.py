"""Users. Spec: docs/03-specs/02-identity-tenancy.md §3.3."""

import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.api_model import ApiModel

router = APIRouter()


class UserPatch(ApiModel):
    status: str | None = None
    attributes: dict[str, object] | None = None


def _user(row: object) -> dict[str, object]:
    return {
        "id": str(row.id),  # type: ignore[attr-defined]
        "email": row.email,  # type: ignore[attr-defined]
        "display_name": row.display_name,  # type: ignore[attr-defined]
        "status": row.status,  # type: ignore[attr-defined]
        "last_login_at": None
        if row.last_login_at is None  # type: ignore[attr-defined]
        else row.last_login_at.isoformat(),  # type: ignore[attr-defined]
        "roles": [],
    }


@router.get("/api/v1/users", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def list_users(
    identity: IdentityDep, q: str | None = None, status: str | None = None
) -> dict[str, object]:
    rows = await identity.store.list_users(status=status, query=q)
    return {"data": [_user(row) for row in rows], "next_cursor": None}


@router.get("/api/v1/users/{user_id}", dependencies=[Depends(require_permission("users:read"))])
@expose(public=False, permission="users:read")
async def get_user(user_id: uuid.UUID, identity: IdentityDep) -> dict[str, object]:
    return _user(await identity._user(user_id))


@router.patch("/api/v1/users/{user_id}", dependencies=[Depends(require_permission("users:manage"))])
@expose(public=False, permission="users:manage")
async def patch_user(
    user_id: uuid.UUID, body: UserPatch, identity: IdentityDep
) -> dict[str, object]:
    row = await identity.patch_user(user_id, status=body.status, attributes=body.attributes)
    return _user(row)

"""SCIM bearer tokens. Spec: docs/03-specs/02-identity-tenancy.md §3.8."""

import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission

router = APIRouter()


@router.get("/api/v1/scim-tokens", dependencies=[Depends(require_permission("tenant:manage"))])
@expose(public=False, permission="tenant:manage")
async def list_tokens(identity: IdentityDep) -> dict[str, object]:
    rows = await identity.store.list_scim_tokens()
    return {"data": [{"id": str(row.id), "prefix": row.prefix} for row in rows]}


@router.post("/api/v1/scim-tokens", dependencies=[Depends(require_permission("tenant:manage"))])
@expose(public=False, permission="tenant:manage")
async def create_token(identity: IdentityDep) -> dict[str, str]:
    row, token = await identity.create_scim_token()
    return {"id": str(row.id), "token": token, "prefix": row.prefix}


@router.delete(
    "/api/v1/scim-tokens/{scim_token_id}",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def delete_token(scim_token_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    for row in await identity.store.list_scim_tokens():
        if row.id == scim_token_id:
            await identity.store.delete(row)
            return {"revoked": True}
    from ar_common.errors import NotFoundError  # noqa: PLC0415

    raise NotFoundError("scim token not found")

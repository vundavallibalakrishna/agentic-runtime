"""API keys. Spec: docs/03-specs/02-identity-tenancy.md §3.8."""

import uuid

from fastapi import APIRouter, Depends
from pydantic import Field

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.json_api import ApiModel

router = APIRouter()


class ApiKeyCreate(ApiModel):
    name: str
    service_account_id: uuid.UUID | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: int = 90


def _row(item: object, secret: str | None = None) -> dict[str, object]:
    body: dict[str, object] = {
        "id": str(item.id),  # type: ignore[attr-defined]
        "name": item.name,  # type: ignore[attr-defined]
        "prefix": item.prefix,  # type: ignore[attr-defined]
        "scopes": list(item.scopes),  # type: ignore[attr-defined]
        "expires_at": None if item.expires_at is None else item.expires_at.isoformat(),  # type: ignore[attr-defined]
    }
    if secret is not None:
        body["key"] = secret
    return body


@router.get("/api/v1/api-keys", dependencies=[Depends(require_permission("api_keys:manage_own"))])
@expose(public=False, permission="api_keys:manage_own")
async def list_api_keys(
    identity: IdentityDep, service_account_id: uuid.UUID | None = None
) -> dict[str, object]:
    user_id = None if service_account_id else identity.ctx.user_id
    rows = await identity.store.list_api_keys(
        user_id=user_id, service_account_id=service_account_id
    )
    return {"data": [_row(row) for row in rows]}


@router.post("/api/v1/api-keys", dependencies=[Depends(require_permission("api_keys:manage_own"))])
@expose(public=False, permission="api_keys:manage_own")
async def create_api_key(body: ApiKeyCreate, identity: IdentityDep) -> dict[str, object]:
    if body.service_account_id is not None and not identity.ctx.principal.allows(
        "service_accounts:manage"
    ):
        from ar_common.errors import ForbiddenError  # noqa: PLC0415

        raise ForbiddenError("service account keys require service_accounts:manage")
    row, secret = await identity.create_api_key(
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
        service_account_id=body.service_account_id,
    )
    return _row(row, secret)


@router.delete(
    "/api/v1/api-keys/{api_key_id}",
    dependencies=[Depends(require_permission("api_keys:manage_own"))],
)
@expose(public=False, permission="api_keys:manage_own")
async def delete_api_key(api_key_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    await identity.revoke_api_key(api_key_id)
    return {"revoked": True}

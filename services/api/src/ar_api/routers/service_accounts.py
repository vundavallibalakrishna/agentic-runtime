"""Service accounts. Spec: docs/03-specs/02-identity-tenancy.md §3.8."""

import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.api_model import ApiModel

router = APIRouter()


class ServiceAccountCreate(ApiModel):
    name: str
    description: str = ""
    allow_on_behalf_of: bool = False


class ServiceAccountPatch(ApiModel):
    description: str | None = None
    status: str | None = None
    allow_on_behalf_of: bool | None = None


def _row(item: object) -> dict[str, object]:
    return {
        "id": str(item.id),  # type: ignore[attr-defined]
        "name": item.name,  # type: ignore[attr-defined]
        "description": item.description,  # type: ignore[attr-defined]
        "status": item.status,  # type: ignore[attr-defined]
        "allow_on_behalf_of": item.allow_on_behalf_of,  # type: ignore[attr-defined]
    }


@router.get(
    "/api/v1/service-accounts",
    dependencies=[Depends(require_permission("service_accounts:manage"))],
)
@expose(public=False, permission="service_accounts:manage")
async def list_service_accounts(identity: IdentityDep) -> dict[str, object]:
    return {"data": [_row(item) for item in await identity.store.list_service_accounts()]}


@router.post(
    "/api/v1/service-accounts",
    dependencies=[Depends(require_permission("service_accounts:manage"))],
)
@expose(public=False, permission="service_accounts:manage")
async def create_service_account(
    body: ServiceAccountCreate, identity: IdentityDep
) -> dict[str, object]:
    row = await identity.create_service_account(
        name=body.name, description=body.description, allow_on_behalf_of=body.allow_on_behalf_of
    )
    return _row(row)


@router.patch(
    "/api/v1/service-accounts/{service_account_id}",
    dependencies=[Depends(require_permission("service_accounts:manage"))],
)
@expose(public=False, permission="service_accounts:manage")
async def patch_service_account(
    service_account_id: uuid.UUID, body: ServiceAccountPatch, identity: IdentityDep
) -> dict[str, object]:
    row = await identity.store.get_service_account(service_account_id)
    if row is None:
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError("service account not found")
    if body.description is not None:
        row.description = body.description
    if body.status is not None:
        row.status = body.status
    if body.allow_on_behalf_of is not None:
        row.allow_on_behalf_of = body.allow_on_behalf_of
    return _row(row)


@router.delete(
    "/api/v1/service-accounts/{service_account_id}",
    dependencies=[Depends(require_permission("service_accounts:manage"))],
)
@expose(public=False, permission="service_accounts:manage")
async def delete_service_account(
    service_account_id: uuid.UUID, identity: IdentityDep
) -> dict[str, bool]:
    row = await identity.store.get_service_account(service_account_id)
    if row is None:
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError("service account not found")
    await identity.store.delete(row)
    return {"deleted": True}

"""Support access grants. Spec: docs/03-specs/02-identity-tenancy.md §3.11."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import IdentityDep, expose, require_permission
from ar_common.errors import NotFoundError
from ar_common.time import utcnow
from ar_contracts.json_api import ApiModel

router = APIRouter()


class GrantCreate(ApiModel):
    operator_subject: str
    operator_email: str
    level: str
    reason: str = Field(min_length=10, max_length=1000)
    hours: int = 8


def _enabled(request: Request) -> None:
    if request.app.state.settings.deployment_mode.value != "saas":
        raise NotFoundError("support access is available in SaaS mode")


@router.get(
    "/api/v1/tenant/support-access", dependencies=[Depends(require_permission("tenant:manage"))]
)
@expose(public=False, permission="tenant:manage")
async def list_grants(request: Request, identity: IdentityDep) -> dict[str, object]:
    _enabled(request)
    now = utcnow()
    rows = await identity.store.list_support_grants()
    return {
        "data": [
            {
                "id": str(row.id),
                "operator_email": row.operator_email,
                "level": row.level,
                "expires_at": row.expires_at.isoformat(),
                "active": row.revoked_at is None and row.expires_at > now,
            }
            for row in rows
        ]
    }


@router.post(
    "/api/v1/tenant/support-access", dependencies=[Depends(require_permission("tenant:manage"))]
)
@expose(public=False, permission="tenant:manage")
async def create_grant(
    body: GrantCreate, request: Request, identity: IdentityDep
) -> dict[str, str]:
    _enabled(request)
    row = await identity.grant_support(
        operator_subject=body.operator_subject,
        operator_email=body.operator_email,
        level=body.level,
        reason=body.reason,
        hours=body.hours,
    )
    return {"id": str(row.id)}


@router.post(
    "/api/v1/tenant/support-access/{grant_id}:revoke",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def revoke_grant(
    grant_id: uuid.UUID, request: Request, identity: IdentityDep
) -> dict[str, bool]:
    _enabled(request)
    for row in await identity.store.list_support_grants():
        if row.id == grant_id:
            row.revoked_at = utcnow()
            return {"revoked": True}
    raise NotFoundError("grant not found")

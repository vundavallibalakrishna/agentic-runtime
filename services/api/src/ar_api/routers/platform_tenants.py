"""Platform tenant administration. Spec: docs/03-specs/02-identity-tenancy.md §3.10."""

import uuid

from fastapi import APIRouter, Request

from ar_api.deps import expose
from ar_api.state import as_object
from ar_common.errors import ForbiddenError, NotFoundError
from ar_contracts.json_api import ApiModel

router = APIRouter()


class TenantCreate(ApiModel):
    slug: str
    name: str
    plan_key: str
    owner_email: str


def _saas(request: Request) -> None:
    if request.app.state.settings.deployment_mode.value != "saas":
        raise NotFoundError("platform routes are not available in single-tenant mode")
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.kind != "platform_admin":
        raise ForbiddenError("platform admin required")


@router.get("/api/v1/platform/tenants")
@expose(public=False, permission=None)
async def list_tenants(request: Request) -> dict[str, object]:
    _saas(request)
    return {"data": await request.app.state.platform.list_tenants()}


@router.post("/api/v1/platform/tenants", status_code=202)
@expose(public=False, permission=None)
async def create_tenant(body: TenantCreate, request: Request) -> dict[str, str]:
    _saas(request)
    tenant_id = await request.app.state.platform.provision(
        body.slug, body.name, body.plan_key, body.owner_email
    )
    return {"tenant_id": tenant_id}


@router.get("/api/v1/platform/tenants/{tenant_id}")
@expose(public=False, permission=None)
async def get_tenant(tenant_id: uuid.UUID, request: Request) -> dict[str, object]:
    _saas(request)
    found = await request.app.state.platform.get_tenant(str(tenant_id))
    if found is None:
        raise NotFoundError("tenant not found")
    return as_object(found)


@router.post("/api/v1/platform/tenants/{tenant_id}:suspend")
@expose(public=False, permission=None)
async def suspend(tenant_id: uuid.UUID, request: Request) -> dict[str, str]:
    _saas(request)
    await request.app.state.platform.set_status(str(tenant_id), "suspended")
    return {"status": "suspended"}


@router.post("/api/v1/platform/tenants/{tenant_id}:resume")
@expose(public=False, permission=None)
async def resume(tenant_id: uuid.UUID, request: Request) -> dict[str, str]:
    _saas(request)
    await request.app.state.platform.set_status(str(tenant_id), "active")
    return {"status": "active"}


@router.post("/api/v1/platform/tenants/{tenant_id}:delete")
@expose(public=False, permission=None)
async def delete_tenant(
    tenant_id: uuid.UUID, request: Request, body: dict[str, str]
) -> dict[str, str]:
    _saas(request)
    await request.app.state.platform.delete(str(tenant_id), body.get("confirm_slug", ""))
    return {"status": "deleting"}

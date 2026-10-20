"""Platform plans. Spec: docs/03-specs/02-identity-tenancy.md §3.10."""

import uuid

from fastapi import APIRouter, Request
from pydantic import Field

from ar_api.deps import expose
from ar_api.state import as_object
from ar_common.errors import ForbiddenError, NotFoundError
from ar_contracts.api_model import ApiModel

router = APIRouter()


class PlanBody(ApiModel):
    key: str
    name: str
    limits: dict[str, object] = Field(default_factory=dict)


def _saas(request: Request) -> None:
    if request.app.state.settings.deployment_mode.value != "saas":
        raise NotFoundError("platform routes are not available in single-tenant mode")
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.kind != "platform_admin":
        raise ForbiddenError("platform admin required")


@router.get("/api/v1/platform/plans")
@expose(public=False, permission=None)
async def list_plans(request: Request) -> dict[str, object]:
    _saas(request)
    return {"data": await request.app.state.platform.list_plans()}


@router.post("/api/v1/platform/plans")
@expose(public=False, permission=None)
async def create_plan(body: PlanBody, request: Request) -> dict[str, object]:
    _saas(request)
    return as_object(
        await request.app.state.platform.save_plan(None, body.key, body.name, body.limits)
    )


@router.patch("/api/v1/platform/plans/{plan_id}")
@expose(public=False, permission=None)
async def patch_plan(plan_id: uuid.UUID, body: PlanBody, request: Request) -> dict[str, object]:
    _saas(request)
    return as_object(
        await request.app.state.platform.save_plan(str(plan_id), body.key, body.name, body.limits)
    )

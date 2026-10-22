"""Segregation of duties. Spec: docs/03-specs/09-policy-approvals.md §12."""

import uuid

from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.approvals.sod import SodBook

router = APIRouter()


class ConstraintBody(ApiModel):
    role_a: str
    role_b: str
    applies_to: str


class ConstraintPatch(ApiModel):
    enabled: bool | None = None
    applies_to: str | None = None


class CheckBody(ApiModel):
    action: str = "approval"
    preparer_principal_id: uuid.UUID | None = None
    signer_principal_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None


@router.get("/api/v1/sod-constraints", dependencies=[Depends(require_permission("policies:read"))])
@expose(public=False, permission="policies:read")
async def list_constraints(request: Request) -> dict[str, object]:
    return page(SodBook(chat(request)).list_constraints(actor(request)))


@router.post("/api/v1/sod-constraints", dependencies=[Depends(require_permission("sod:manage"))])
@expose(public=False, permission="sod:manage")
async def create_constraint(body: ConstraintBody, request: Request) -> dict[str, object]:
    return SodBook(chat(request)).create_constraint(actor(request), dump(body))


@router.post(
    "/api/v1/sod-constraints:check", dependencies=[Depends(require_permission("policies:read"))]
)
@expose(public=False, permission="policies:read")
async def check_constraint(body: CheckBody, request: Request) -> dict[str, object]:
    return SodBook(chat(request)).check(actor(request), dump(body))


@router.get(
    "/api/v1/sod-constraints/{constraint_id}",
    dependencies=[Depends(require_permission("policies:read"))],
)
@expose(public=False, permission="policies:read")
async def get_constraint(constraint_id: uuid.UUID, request: Request) -> dict[str, object]:
    return SodBook(chat(request)).get_constraint(actor(request), constraint_id)


@router.patch(
    "/api/v1/sod-constraints/{constraint_id}",
    dependencies=[Depends(require_permission("sod:manage"))],
)
@expose(public=False, permission="sod:manage")
async def patch_constraint(
    constraint_id: uuid.UUID, body: ConstraintPatch, request: Request
) -> dict[str, object]:
    return SodBook(chat(request)).patch_constraint(actor(request), constraint_id, dump(body))


@router.delete(
    "/api/v1/sod-constraints/{constraint_id}",
    dependencies=[Depends(require_permission("sod:manage"))],
)
@expose(public=False, permission="sod:manage")
async def delete_constraint(constraint_id: uuid.UUID, request: Request) -> dict[str, bool]:
    SodBook(chat(request)).delete_constraint(actor(request), constraint_id)
    return {"deleted": True}

"""Policy authoring and simulation. Spec: docs/03-specs/09-policy-approvals.md §4."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page, stepped_up
from ar_contracts.api_model import ApiModel
from ar_domain.policy.service import PolicyBook

router = APIRouter()


class PolicyBody(ApiModel):
    name: str = ""
    description: str = ""
    kind: str = "rules"
    priority: int = 100
    document: dict[str, object] | None = None
    rego: str | None = None


class PolicyPatch(ApiModel):
    name: str | None = None
    description: str | None = None
    priority: int | None = None


class ActivateBody(ApiModel):
    version: int


class SimulateBody(ApiModel):
    tool_qualified_name: str = ""
    tool_call_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    args: dict[str, object] = Field(default_factory=dict)
    include_drafts: list[uuid.UUID] = Field(default_factory=list)
    trigger: str = "chat"
    channel: str = "web"


@router.get("/api/v1/policies", dependencies=[Depends(require_permission("policies:read"))])
@expose(public=False, permission="policies:read")
async def list_policies(request: Request) -> dict[str, object]:
    return page(PolicyBook(chat(request)).list_policies(actor(request)))


@router.post("/api/v1/policies", dependencies=[Depends(require_permission("policies:manage"))])
@expose(public=False, permission="policies:manage")
async def create_policy(body: PolicyBody, request: Request) -> dict[str, object]:
    return PolicyBook(chat(request)).create(actor(request), dump(body))


@router.post(
    "/api/v1/policies:simulate", dependencies=[Depends(require_permission("policies:read"))]
)
@expose(public=False, permission="policies:read")
async def simulate_policy(body: SimulateBody, request: Request) -> dict[str, object]:
    return PolicyBook(chat(request)).simulate(actor(request), dump(body))


@router.get(
    "/api/v1/policies/{policy_id}", dependencies=[Depends(require_permission("policies:read"))]
)
@expose(public=False, permission="policies:read")
async def get_policy(policy_id: uuid.UUID, request: Request) -> dict[str, object]:
    return PolicyBook(chat(request)).get(actor(request), policy_id)


@router.patch(
    "/api/v1/policies/{policy_id}", dependencies=[Depends(require_permission("policies:manage"))]
)
@expose(public=False, permission="policies:manage")
async def patch_policy(
    policy_id: uuid.UUID, body: PolicyPatch, request: Request
) -> dict[str, object]:
    return PolicyBook(chat(request)).patch(actor(request), policy_id, dump(body))


@router.delete(
    "/api/v1/policies/{policy_id}", dependencies=[Depends(require_permission("policies:manage"))]
)
@expose(public=False, permission="policies:manage")
async def delete_policy(policy_id: uuid.UUID, request: Request) -> dict[str, bool]:
    PolicyBook(chat(request)).delete(actor(request), policy_id)
    return {"deleted": True}


@router.get(
    "/api/v1/policies/{policy_id}/versions",
    dependencies=[Depends(require_permission("policies:read"))],
)
@expose(public=False, permission="policies:read")
async def list_versions(policy_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(PolicyBook(chat(request)).versions(actor(request), policy_id))


@router.post(
    "/api/v1/policies/{policy_id}/versions",
    dependencies=[Depends(require_permission("policies:manage"))],
)
@expose(public=False, permission="policies:manage")
async def add_version(
    policy_id: uuid.UUID, body: PolicyBody, request: Request
) -> dict[str, object]:
    return PolicyBook(chat(request)).add_version(actor(request), policy_id, dump(body))


@router.post(
    "/api/v1/policies/{policy_id}:activate",
    dependencies=[Depends(require_permission("policies:manage"))],
)
@expose(public=False, permission="policies:manage")
async def activate_policy(
    policy_id: uuid.UUID, body: ActivateBody, request: Request
) -> dict[str, object]:
    return PolicyBook(chat(request)).activate(
        actor(request), policy_id, body.version, stepped_up=stepped_up(request)
    )


@router.post(
    "/api/v1/policies/{policy_id}:disable",
    dependencies=[Depends(require_permission("policies:manage"))],
)
@expose(public=False, permission="policies:manage")
async def disable_policy(policy_id: uuid.UUID, request: Request) -> dict[str, object]:
    return PolicyBook(chat(request)).disable(actor(request), policy_id)

"""Standing approvals. Spec: docs/03-specs/09-policy-approvals.md §6."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.approvals.service import ApprovalBook

router = APIRouter()


class StandingBody(ApiModel):
    tool_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    routine_id: uuid.UUID | None = None
    argument_constraints: list[dict[str, object]] = Field(default_factory=list)
    max_uses: int | None = None
    expires_at: datetime


@router.get(
    "/api/v1/standing-approvals",
    dependencies=[Depends(require_permission("approvals:grant_standing"))],
)
@expose(public=False, permission="approvals:grant_standing")
async def list_standing(request: Request) -> dict[str, object]:
    return page(ApprovalBook(chat(request)).list_standing(actor(request)))


@router.post(
    "/api/v1/standing-approvals",
    dependencies=[Depends(require_permission("approvals:grant_standing"))],
)
@expose(public=False, permission="approvals:grant_standing")
async def grant_standing(body: StandingBody, request: Request) -> dict[str, object]:
    return ApprovalBook(chat(request)).grant_standing(actor(request), dump(body))


@router.post(
    "/api/v1/standing-approvals/{standing_approval_id}:revoke",
    dependencies=[Depends(require_permission("approvals:grant_standing"))],
)
@expose(public=False, permission="approvals:grant_standing")
async def revoke_standing(standing_approval_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ApprovalBook(chat(request)).revoke_standing(actor(request), standing_approval_id)

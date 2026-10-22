"""Approvals inbox. Spec: docs/03-specs/09-policy-approvals.md §5."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page, stepped_up
from ar_contracts.api_model import ApiModel
from ar_domain.approvals.service import ApprovalBook

router = APIRouter()


class ApprovalDecideBody(ApiModel):
    decision: str
    comment: str = ""
    args_hash: str
    arguments: dict[str, object] | None = None


@router.get("/api/v1/approvals", dependencies=[Depends(require_permission("approvals:decide"))])
@expose(public=False, permission="approvals:decide")
async def list_approvals(
    request: Request,
    scope: Annotated[str, Query()] = "to_decide",
    status: Annotated[str | None, Query()] = None,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    risk_class: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    rows = ApprovalBook(chat(request)).list_items(
        actor(request),
        scope=scope,
        status=status,
        agent_id=agent_id,
        risk_class=risk_class,
    )
    return page(rows)


@router.get(
    "/api/v1/approvals/{approval_id}",
    dependencies=[Depends(require_permission("approvals:decide"))],
)
@expose(public=False, permission="approvals:decide")
async def get_approval(approval_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ApprovalBook(chat(request)).get(actor(request), approval_id)


@router.post(
    "/api/v1/approvals/{approval_id}:decide",
    dependencies=[Depends(require_permission("approvals:decide"))],
)
@expose(public=False, permission="approvals:decide")
async def decide_approval(
    approval_id: uuid.UUID, body: ApprovalDecideBody, request: Request
) -> dict[str, object]:
    return ApprovalBook(chat(request)).decide(
        actor(request), approval_id, dump(body), stepped_up=stepped_up(request)
    )


@router.post(
    "/api/v1/approvals/{approval_id}:cancel",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def cancel_approval(approval_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ApprovalBook(chat(request)).cancel(actor(request), approval_id)

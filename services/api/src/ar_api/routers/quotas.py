"""Quota catalogue. Spec: docs/03-specs/17-audit-usage-metering.md §2.4."""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.usage.service import UsageBook

router = APIRouter()


class QuotaBody(ApiModel):
    scope_type: str
    scope_id: uuid.UUID | None = None
    metric: str
    period: str
    limit_value: int
    action: str = "block"
    warn_at_pct: int = 80


class QuotaPatch(ApiModel):
    limit_value: int | None = None
    action: str | None = None
    warn_at_pct: int | None = None


def _book(request: Request) -> UsageBook:
    return UsageBook(chat(request))


@router.get("/api/v1/quotas", dependencies=[Depends(require_permission("usage:read"))])
@expose(public=False, permission="usage:read")
async def list_quotas(request: Request) -> dict[str, object]:
    return page(_book(request).list_quotas(actor(request)))


@router.post(
    "/api/v1/quotas",
    status_code=201,
    dependencies=[Depends(require_permission("quotas:manage"))],
)
@expose(public=False, permission="quotas:manage")
async def create_quota(body: QuotaBody, request: Request) -> dict[str, object]:
    return _book(request).create(actor(request), dump(body))


@router.patch(
    "/api/v1/quotas/{quota_id}",
    dependencies=[Depends(require_permission("quotas:manage"))],
)
@expose(public=False, permission="quotas:manage")
async def patch_quota(quota_id: uuid.UUID, body: QuotaPatch, request: Request) -> dict[str, object]:
    return _book(request).update(actor(request), quota_id, dump(body))


@router.delete(
    "/api/v1/quotas/{quota_id}",
    status_code=204,
    dependencies=[Depends(require_permission("quotas:manage"))],
)
@expose(public=False, permission="quotas:manage")
async def delete_quota(quota_id: uuid.UUID, request: Request) -> Response:
    _book(request).delete(actor(request), quota_id)
    return Response(status_code=204)

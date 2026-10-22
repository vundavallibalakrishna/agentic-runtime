"""Cross-tenant usage for SaaS operators. Spec: docs/03-specs/17-audit-usage-metering.md §2.4."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from ar_api.deps import expose
from ar_api.routers.tooling import chat
from ar_common.errors import ForbiddenError, NotFoundError
from ar_domain.usage.service import UsageBook

router = APIRouter()


def _saas(request: Request) -> None:
    if request.app.state.settings.deployment_mode.value != "saas":
        raise NotFoundError("platform routes are not available in single-tenant mode")
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.kind != "platform_admin":
        raise ForbiddenError("platform admin required")


def _query(*, group_by: str, start: str | None, end: str | None) -> dict[str, str]:
    raw = {"group_by": group_by, "from": start or "", "to": end or ""}
    return {key: value for key, value in raw.items() if value}


@router.get("/api/v1/platform/usage")
@expose(public=False, permission=None)
async def platform_usage(
    request: Request,
    *,
    group_by: Annotated[str, Query()] = "tenant",
    start: Annotated[str | None, Query(alias="from")] = None,
    end: Annotated[str | None, Query(alias="to")] = None,
) -> dict[str, object]:
    _saas(request)
    return UsageBook(chat(request)).platform_summary(
        _query(group_by=group_by, start=start, end=end)
    )


@router.get("/api/v1/platform/usage/export")
@expose(public=False, permission=None)
async def platform_export(
    request: Request,
    *,
    group_by: Annotated[str, Query()] = "tenant",
    start: Annotated[str | None, Query(alias="from")] = None,
    end: Annotated[str | None, Query(alias="to")] = None,
) -> Response:
    _saas(request)
    body = UsageBook(chat(request)).platform_export(_query(group_by=group_by, start=start, end=end))
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="platform-usage.csv"'},
    )

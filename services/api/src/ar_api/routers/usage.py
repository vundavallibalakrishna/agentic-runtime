"""Usage summaries and chargeback export. Spec: docs/03-specs/17-audit-usage-metering.md §2.4."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat
from ar_domain.usage.service import UsageBook

router = APIRouter()


def _book(request: Request) -> UsageBook:
    return UsageBook(chat(request))


def _query(
    *,
    group_by: str,
    start: str | None,
    end: str | None,
    metric: str | None,
    agent_id: str | None,
    user_id: str | None,
    team_id: str | None,
) -> dict[str, str]:
    raw = {
        "group_by": group_by,
        "from": start or "",
        "to": end or "",
        "metric": metric or "",
        "agent_id": agent_id or "",
        "user_id": user_id or "",
        "team_id": team_id or "",
    }
    return {key: value for key, value in raw.items() if value}


@router.get("/api/v1/usage/summary", dependencies=[Depends(require_permission("usage:read"))])
@expose(public=False, permission="usage:read")
async def usage_summary(
    request: Request,
    *,
    group_by: Annotated[str, Query()] = "day",
    start: Annotated[str | None, Query(alias="from")] = None,
    end: Annotated[str | None, Query(alias="to")] = None,
    metric: Annotated[str | None, Query()] = None,
    agent_id: Annotated[str | None, Query()] = None,
    user_id: Annotated[str | None, Query()] = None,
    team_id: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    query = _query(
        group_by=group_by,
        start=start,
        end=end,
        metric=metric,
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
    )
    return _book(request).summary(actor(request), query)


@router.get("/api/v1/usage/export", dependencies=[Depends(require_permission("usage:read"))])
@expose(public=False, permission="usage:read")
async def usage_export(
    request: Request,
    *,
    group_by: Annotated[str, Query()] = "day",
    start: Annotated[str | None, Query(alias="from")] = None,
    end: Annotated[str | None, Query(alias="to")] = None,
    metric: Annotated[str | None, Query()] = None,
    agent_id: Annotated[str | None, Query()] = None,
    user_id: Annotated[str | None, Query()] = None,
    team_id: Annotated[str | None, Query()] = None,
) -> Response:
    query = _query(
        group_by=group_by,
        start=start,
        end=end,
        metric=metric,
        agent_id=agent_id,
        user_id=user_id,
        team_id=team_id,
    )
    body = _book(request).export_csv(actor(request), query)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="usage.csv"'},
    )


@router.get("/api/v1/me/usage")
@expose(public=False, permission=None)
async def my_usage(request: Request) -> dict[str, object]:
    return _book(request).mine(actor(request))

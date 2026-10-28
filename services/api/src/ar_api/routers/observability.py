"""Observability overview. Spec: docs/03-specs/18-observability-eval.md §3."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat
from ar_common.errors import ValidationFailedError
from ar_domain.evals.book import public_row
from ar_domain.runs.service import overview

router = APIRouter()


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationFailedError("date is invalid") from exc


@router.get(
    "/api/v1/observability/overview",
    dependencies=[Depends(require_permission("usage:read"))],
)
@expose(public=False, permission="usage:read")
async def observability_overview(
    request: Request,
    *,
    start: Annotated[str | None, Query(alias="from")] = None,
    end: Annotated[str | None, Query(alias="to")] = None,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    caller = actor(request)
    body = overview(
        chat(request),
        caller.tenant_id,
        start=_when(start),
        end=_when(end),
        agent_id=agent_id,
    )
    return public_row(body)

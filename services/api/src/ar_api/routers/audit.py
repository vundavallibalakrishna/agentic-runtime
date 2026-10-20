"""Audit read API. Spec: docs/03-specs/17-audit-usage-metering.md §1.3."""

from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_api.state import as_object
from ar_common.errors import NotFoundError

router = APIRouter()


@router.get("/api/v1/audit-events", dependencies=[Depends(require_permission("audit:read"))])
@expose(public=False, permission="audit:read")
async def list_events(request: Request) -> dict[str, object]:
    data = await request.app.state.audit_api.list_events()
    return {"data": data, "next_cursor": None}


@router.get(
    "/api/v1/audit-events/{event_id}", dependencies=[Depends(require_permission("audit:read"))]
)
@expose(public=False, permission="audit:read")
async def get_event(event_id: int, request: Request) -> dict[str, object]:
    found = await request.app.state.audit_api.get(event_id)
    if found is None:
        raise NotFoundError("audit event not found")
    return as_object(found)


@router.post(
    "/api/v1/audit-events:verify", dependencies=[Depends(require_permission("audit:read"))]
)
@expose(public=False, permission="audit:read")
async def verify(request: Request) -> dict[str, object]:
    return as_object(await request.app.state.audit_api.verify())

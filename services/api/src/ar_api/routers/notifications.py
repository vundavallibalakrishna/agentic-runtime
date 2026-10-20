"""Notifications. Spec: docs/03-specs/20-notifications-events.md §2."""

import uuid
from collections.abc import AsyncIterator  # noqa: TC003

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from ar_api.deps import expose
from ar_common.errors import NotFoundError

router = APIRouter()


@router.get("/api/v1/notifications")
@expose(public=False, permission=None)
async def list_notifications(request: Request) -> dict[str, object]:
    return {"data": await request.app.state.notifications.list_items()}


@router.post("/api/v1/notifications/{notification_id}:read")
@expose(public=False, permission=None)
async def mark_read(notification_id: uuid.UUID, request: Request) -> dict[str, bool]:
    if not await request.app.state.notifications.read(str(notification_id)):
        raise NotFoundError("notification not found")
    return {"read": True}


@router.post("/api/v1/notifications:read-all")
@expose(public=False, permission=None)
async def read_all(request: Request) -> dict[str, int]:
    return {"updated": await request.app.state.notifications.read_all()}


@router.get("/api/v1/notifications/events")
@expose(public=False, permission=None)
async def events(request: Request) -> EventSourceResponse:
    async def generate() -> AsyncIterator[dict[str, str]]:
        rows = await request.app.state.notifications.list_items()
        for item in rows:
            title = item.get("title", "") if isinstance(item, dict) else ""
            yield {"event": "notification", "data": str(title)}

    return EventSourceResponse(generate())

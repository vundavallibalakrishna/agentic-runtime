"""Notifications. Spec: docs/03-specs/20-notifications-events.md §2."""

import uuid
from collections.abc import AsyncIterator  # noqa: TC003

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from ar_api.deps import expose
from ar_common.errors import NotFoundError, UnauthenticatedError
from ar_contracts.api_model import ApiModel

router = APIRouter()


class PushBody(ApiModel):
    endpoint: str
    content_encoding: str = "aes128gcm"


def _person(request: Request) -> tuple[object, object]:
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.tenant_id is None:
        raise UnauthenticatedError()
    return principal.tenant_id, principal.id


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


@router.post("/api/v1/notifications/push-subscriptions")
@expose(public=False, permission=None)
async def create_push_subscription(body: PushBody, request: Request) -> dict[str, object]:
    from ar_domain.notifications.dispatch import subscribe  # noqa: PLC0415

    tenant_id, user_id = _person(request)
    import uuid as uuid_mod  # noqa: PLC0415

    return subscribe(
        request.app.state.chat,
        tenant_id=uuid_mod.UUID(str(tenant_id)),
        user_id=uuid_mod.UUID(str(user_id)),
        endpoint=body.endpoint,
        encoding=body.content_encoding,
    )


@router.delete("/api/v1/notifications/push-subscriptions/{subscription_id}")
@expose(public=False, permission=None)
async def delete_push_subscription(subscription_id: uuid.UUID, request: Request) -> dict[str, bool]:
    from ar_domain.notifications.dispatch import unsubscribe  # noqa: PLC0415

    tenant_id, _user_id = _person(request)
    import uuid as uuid_mod  # noqa: PLC0415

    removed = unsubscribe(
        request.app.state.chat,
        tenant_id=uuid_mod.UUID(str(tenant_id)),
        subscription_id=subscription_id,
    )
    if not removed:
        raise NotFoundError("subscription not found")
    return {"deleted": True}


@router.get("/api/v1/notifications/events")
@expose(public=False, permission=None)
async def events(request: Request) -> EventSourceResponse:
    async def generate() -> AsyncIterator[dict[str, str]]:
        rows = await request.app.state.notifications.list_items()
        for item in rows:
            title = item.get("title", "") if isinstance(item, dict) else ""
            yield {"event": "notification", "data": str(title)}

    return EventSourceResponse(generate())

"""Outbound webhooks. Spec: docs/03-specs/20-notifications-events.md §3."""

import uuid

from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_api.state import as_object
from ar_common.errors import NotFoundError
from ar_common.http import assert_public_url
from ar_contracts.api_model import ApiModel

router = APIRouter()


class WebhookCreate(ApiModel):
    name: str
    url: str
    topics: list[str]


@router.get("/api/v1/webhooks", dependencies=[Depends(require_permission("webhooks:manage"))])
@expose(public=False, permission="webhooks:manage")
async def list_webhooks(request: Request) -> dict[str, object]:
    return {"data": await request.app.state.webhooks.list_hooks()}


@router.post("/api/v1/webhooks", dependencies=[Depends(require_permission("webhooks:manage"))])
@expose(public=False, permission="webhooks:manage")
async def create_webhook(body: WebhookCreate, request: Request) -> dict[str, object]:
    _check_url(body.url, allow_private=bool(request.app.state.settings.webhook_allow_private))
    return as_object(await request.app.state.webhooks.create(body.name, body.url, body.topics))


@router.get(
    "/api/v1/webhooks/{webhook_id}", dependencies=[Depends(require_permission("webhooks:manage"))]
)
@expose(public=False, permission="webhooks:manage")
async def get_webhook(webhook_id: uuid.UUID, request: Request) -> dict[str, object]:
    found = await request.app.state.webhooks.get(str(webhook_id))
    if found is None:
        raise NotFoundError("webhook not found")
    return as_object(found)


@router.patch(
    "/api/v1/webhooks/{webhook_id}", dependencies=[Depends(require_permission("webhooks:manage"))]
)
@expose(public=False, permission="webhooks:manage")
async def patch_webhook(
    webhook_id: uuid.UUID, body: WebhookCreate, request: Request
) -> dict[str, object]:
    _check_url(body.url, allow_private=bool(request.app.state.settings.webhook_allow_private))
    found = await request.app.state.webhooks.update(
        str(webhook_id), body.name, body.url, body.topics
    )
    if found is None:
        raise NotFoundError("webhook not found")
    return as_object(found)


@router.delete(
    "/api/v1/webhooks/{webhook_id}", dependencies=[Depends(require_permission("webhooks:manage"))]
)
@expose(public=False, permission="webhooks:manage")
async def delete_webhook(webhook_id: uuid.UUID, request: Request) -> dict[str, bool]:
    if not await request.app.state.webhooks.delete(str(webhook_id)):
        raise NotFoundError("webhook not found")
    return {"deleted": True}


@router.post(
    "/api/v1/webhooks/{webhook_id}:rotate-secret",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def rotate(webhook_id: uuid.UUID, request: Request) -> dict[str, str]:
    secret = await request.app.state.webhooks.rotate(str(webhook_id))
    if secret is None:
        raise NotFoundError("webhook not found")
    return {"secret": secret}


@router.post(
    "/api/v1/webhooks/{webhook_id}:test",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def test_webhook(webhook_id: uuid.UUID, request: Request) -> dict[str, str]:
    await request.app.state.webhooks.enqueue_test(str(webhook_id))
    return {"status": "queued"}


@router.get(
    "/api/v1/webhooks/{webhook_id}/deliveries",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def deliveries(webhook_id: uuid.UUID, request: Request) -> dict[str, object]:
    return {"data": await request.app.state.webhooks.deliveries(str(webhook_id))}


@router.post(
    "/api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}:redeliver",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def redeliver(
    webhook_id: uuid.UUID, delivery_id: uuid.UUID, request: Request
) -> dict[str, str]:
    del webhook_id
    await request.app.state.webhooks.redeliver(str(delivery_id))
    return {"status": "queued"}


@router.post(
    "/api/v1/tenant/run-callback-secret:rotate",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def rotate_callback(request: Request) -> dict[str, str]:
    return {"secret": await request.app.state.webhooks.rotate_callback()}


def _check_url(url: str, *, allow_private: bool) -> None:
    if allow_private:
        return
    assert_public_url(url)

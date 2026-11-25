"""Outbound webhooks. Spec: docs/03-specs/20-notifications-events.md §3."""

import uuid

from fastapi import APIRouter, Depends, Request

from ar_api.deps import current_principal, expose, require_permission
from ar_common.errors import NotFoundError
from ar_common.http import assert_public_url
from ar_contracts.api_model import ApiModel
from ar_domain.webhooks.book import WebhookBook
from ar_domain.webhooks.delivery import _start_or_attempt

router = APIRouter()


class WebhookCreate(ApiModel):
    name: str
    url: str
    topics: list[str]


def _book(request: Request) -> tuple[WebhookBook, uuid.UUID, uuid.UUID | None]:
    principal = current_principal(request)
    tenant_id = principal.tenant_id
    if not isinstance(tenant_id, uuid.UUID):
        raise NotFoundError("webhook not found")
    try:
        user_id = uuid.UUID(str(principal.id))
    except ValueError:
        user_id = None
    return WebhookBook(request.app.state.chat), tenant_id, user_id


@router.get("/api/v1/webhooks", dependencies=[Depends(require_permission("webhooks:manage"))])
@expose(public=False, permission="webhooks:manage")
async def list_webhooks(request: Request) -> dict[str, object]:
    book, tenant_id, _user = _book(request)
    return {"data": book.list_hooks(tenant_id)}


@router.post("/api/v1/webhooks", dependencies=[Depends(require_permission("webhooks:manage"))])
@expose(public=False, permission="webhooks:manage")
async def create_webhook(body: WebhookCreate, request: Request) -> dict[str, object]:
    _check_url(body.url, allow_private=bool(request.app.state.settings.webhook_allow_private))
    book, tenant_id, user_id = _book(request)
    return book.create(tenant_id, user_id, body.name, body.url, body.topics)


@router.get(
    "/api/v1/webhooks/{webhook_id}", dependencies=[Depends(require_permission("webhooks:manage"))]
)
@expose(public=False, permission="webhooks:manage")
async def get_webhook(webhook_id: uuid.UUID, request: Request) -> dict[str, object]:
    book, tenant_id, _user = _book(request)
    return book.get(tenant_id, webhook_id)


@router.patch(
    "/api/v1/webhooks/{webhook_id}", dependencies=[Depends(require_permission("webhooks:manage"))]
)
@expose(public=False, permission="webhooks:manage")
async def patch_webhook(
    webhook_id: uuid.UUID, body: WebhookCreate, request: Request
) -> dict[str, object]:
    _check_url(body.url, allow_private=bool(request.app.state.settings.webhook_allow_private))
    book, tenant_id, _user = _book(request)
    return book.update(tenant_id, webhook_id, body.name, body.url, body.topics)


@router.delete(
    "/api/v1/webhooks/{webhook_id}", dependencies=[Depends(require_permission("webhooks:manage"))]
)
@expose(public=False, permission="webhooks:manage")
async def delete_webhook(webhook_id: uuid.UUID, request: Request) -> dict[str, bool]:
    book, tenant_id, _user = _book(request)
    if not book.delete(tenant_id, webhook_id):
        raise NotFoundError("webhook not found")
    return {"deleted": True}


@router.post(
    "/api/v1/webhooks/{webhook_id}:rotate-secret",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def rotate(webhook_id: uuid.UUID, request: Request) -> dict[str, str]:
    book, tenant_id, _user = _book(request)
    return {"secret": book.rotate(tenant_id, webhook_id)}


@router.post(
    "/api/v1/webhooks/{webhook_id}:test",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def test_webhook(webhook_id: uuid.UUID, request: Request) -> dict[str, str]:
    book, tenant_id, _user = _book(request)
    book.get(tenant_id, webhook_id)
    made = book.enqueue(
        tenant_id, "webhook.test", {"webhook_id": str(webhook_id)}, webhook_id=webhook_id
    )
    for row in made:
        delivery_id = row.get("id")
        if isinstance(delivery_id, uuid.UUID):
            _start_or_attempt(request.app.state.chat, delivery_id)
    return {"status": "queued"}


@router.get(
    "/api/v1/webhooks/{webhook_id}/deliveries",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def deliveries(webhook_id: uuid.UUID, request: Request) -> dict[str, object]:
    book, tenant_id, _user = _book(request)
    return {"data": book.deliveries(tenant_id, webhook_id)}


@router.post(
    "/api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}:redeliver",
    dependencies=[Depends(require_permission("webhooks:manage"))],
)
@expose(public=False, permission="webhooks:manage")
async def redeliver(
    webhook_id: uuid.UUID, delivery_id: uuid.UUID, request: Request
) -> dict[str, str]:
    book, tenant_id, _user = _book(request)
    created = book.redeliver(tenant_id, webhook_id, delivery_id)
    new_id = created.get("id")
    if isinstance(new_id, uuid.UUID):
        _start_or_attempt(request.app.state.chat, new_id)
    return {"status": "queued"}


@router.post(
    "/api/v1/tenant/run-callback-secret:rotate",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def rotate_callback(request: Request) -> dict[str, str]:
    from ar_api.deps import current_principal  # noqa: PLC0415

    secret = request.app.state.webhooks.mint_callback_secret()
    principal = current_principal(request)
    if principal.tenant_id is not None:
        await _store_callback_secret(request, principal, secret)
    else:
        request.app.state.webhooks.apply_callback_secret(secret)
    return {"secret": secret}


async def _store_callback_secret(request: Request, principal: object, secret: str) -> None:
    """Commit the secret, then install it. A failed write leaves the old secret."""
    from ar_domain.audit.actions import AuditAction  # noqa: PLC0415
    from ar_domain.audit.memory import remember  # noqa: PLC0415
    from ar_domain.tools.named_secrets import (  # noqa: PLC0415
        install_named_secret,
        stage_named_secret,
        write_named_secret,
    )

    chat = request.app.state.chat
    webhooks = request.app.state.webhooks
    tenant_id = getattr(principal, "tenant_id", None)
    detail: dict[str, object] = {"name": "__run_callback_secret__"}
    engine = getattr(chat, "durable_engine", None)
    if not isinstance(tenant_id, uuid.UUID):
        webhooks.apply_callback_secret(secret)
        return
    if engine is None:
        write_named_secret(chat, tenant_id, "__run_callback_secret__", secret)
        remember(
            chat,
            tenant_id=tenant_id,
            actor_id=getattr(principal, "id", None),
            action=AuditAction.TENANT_RUN_CALLBACK_SECRET_ROTATED,
            target_type="tenant",
            target_id=str(tenant_id or ""),
            detail=detail,
        )
        webhooks.apply_callback_secret(secret)
        return
    from ar_domain.audit.service import record  # noqa: PLC0415
    from ar_domain.db.context import Principal, TenantContext  # noqa: PLC0415
    from ar_domain.db.session import tenant_session  # noqa: PLC0415
    from ar_domain.durable.m26 import upsert_named_secret  # noqa: PLC0415

    if not isinstance(principal, Principal):
        webhooks.apply_callback_secret(secret)
        return
    row = stage_named_secret(tenant_id, "__run_callback_secret__", secret)
    ctx = TenantContext.from_principal(principal, str(getattr(request.state, "request_id", "")))
    async with tenant_session(ctx, engine=engine) as session:
        await upsert_named_secret(session, row)
        await record(
            session,
            tenant_id=principal.tenant_id,
            actor_type=principal.kind,
            actor_id=str(principal.id),
            action=AuditAction.TENANT_RUN_CALLBACK_SECRET_ROTATED,
            target_type="tenant",
            target_id=str(principal.tenant_id),
            detail=detail,
        )
    install_named_secret(chat, row)
    webhooks.apply_callback_secret(secret)


def _check_url(url: str, *, allow_private: bool) -> None:
    if allow_private:
        return
    assert_public_url(url)

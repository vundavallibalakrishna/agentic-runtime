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
    from ar_api.deps import current_principal  # noqa: PLC0415
    from ar_domain.tools.named_secrets import write_named_secret  # noqa: PLC0415

    secret = await request.app.state.webhooks.rotate_callback()
    principal = current_principal(request)
    if principal.tenant_id is not None:
        write_named_secret(
            request.app.state.chat,
            principal.tenant_id,
            "__run_callback_secret__",
            secret,
        )
        await _audit_callback_secret(request, principal)
    return {"secret": secret}


async def _audit_callback_secret(request: Request, principal: object) -> None:
    """Record the rotation. The secret value is not in the event."""
    from ar_domain.audit.actions import AuditAction  # noqa: PLC0415
    from ar_domain.audit.memory import remember  # noqa: PLC0415

    chat = request.app.state.chat
    detail: dict[str, object] = {"name": "__run_callback_secret__"}
    engine = getattr(chat, "durable_engine", None)
    if engine is None:
        remember(
            chat,
            tenant_id=getattr(principal, "tenant_id", None),
            actor_id=getattr(principal, "id", None),
            action=AuditAction.TENANT_RUN_CALLBACK_SECRET_ROTATED,
            target_type="tenant",
            target_id=str(getattr(principal, "tenant_id", "")),
            detail=detail,
        )
        return
    from ar_domain.audit.service import record  # noqa: PLC0415
    from ar_domain.db.context import Principal, TenantContext  # noqa: PLC0415
    from ar_domain.db.session import tenant_session  # noqa: PLC0415

    if not isinstance(principal, Principal) or principal.tenant_id is None:
        return
    ctx = TenantContext.from_principal(principal, str(getattr(request.state, "request_id", "")))
    async with tenant_session(ctx, engine=engine) as session:
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


def _check_url(url: str, *, allow_private: bool) -> None:
    if allow_private:
        return
    assert_public_url(url)

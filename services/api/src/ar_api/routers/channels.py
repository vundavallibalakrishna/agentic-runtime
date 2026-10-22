"""Channel integration API. Spec: docs/03-specs/16-channels.md §5."""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.channels.book import ChannelBook
from ar_domain.channels.service import handle_inbound

router = APIRouter()


class CredentialsBody(ApiModel):
    bot_token: str | None = None
    signing_secret: str | None = None
    app_token: str | None = None
    app_id: str | None = None
    app_password: str | None = None
    tenant_id: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    username: str | None = None
    password: str | None = None
    address: str | None = None
    widget_secret: str | None = None
    secret: str | None = None


class IntegrationBody(ApiModel):
    kind: str
    name: str
    config: dict[str, object] = Field(default_factory=dict)
    credentials: CredentialsBody | None = None
    default_agent_id: uuid.UUID | None = None
    agent_routing: list[dict[str, object]] = Field(default_factory=list)


class IntegrationPatch(ApiModel):
    name: str | None = None
    config: dict[str, object] | None = None
    credentials: CredentialsBody | None = None
    default_agent_id: uuid.UUID | None = None
    agent_routing: list[dict[str, object]] | None = None
    status: str | None = None


class LinkBody(ApiModel):
    token: str


class InboundBody(ApiModel):
    integration_id: uuid.UUID
    kind: str
    event_id: str = ""
    external_user_id: str = ""
    external_user_email: str | None = None
    external_channel_id: str = ""
    external_thread_id: str = ""
    external_message_id: str = ""
    text: str = ""
    is_dm: bool = False
    mentions_bot: bool = False
    command: dict[str, str] | None = None


class ApprovalBody(ApiModel):
    approval_id: uuid.UUID
    decision: str
    args_hash: str = ""
    external_user_id: str = ""
    integration_id: uuid.UUID | None = None


def _book(request: Request) -> ChannelBook:
    return ChannelBook(chat(request))


@router.get(
    "/api/v1/channel-integrations",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def list_integrations(request: Request) -> dict[str, object]:
    return page(_book(request).list_integrations(actor(request)))


@router.post(
    "/api/v1/channel-integrations",
    status_code=201,
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def create_integration(body: IntegrationBody, request: Request) -> dict[str, object]:
    return _book(request).create(actor(request), dump(body))


@router.get(
    "/api/v1/channel-integrations/{integration_id}",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def get_integration(integration_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get(actor(request), integration_id)


@router.patch(
    "/api/v1/channel-integrations/{integration_id}",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def patch_integration(
    integration_id: uuid.UUID, body: IntegrationPatch, request: Request
) -> dict[str, object]:
    return _book(request).patch(actor(request), integration_id, dump(body))


@router.delete(
    "/api/v1/channel-integrations/{integration_id}",
    status_code=204,
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def delete_integration(integration_id: uuid.UUID, request: Request) -> Response:
    _book(request).delete(actor(request), integration_id)
    return Response(status_code=204)


@router.post(
    "/api/v1/channel-integrations/{integration_id}:test",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def test_integration(integration_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).test(actor(request), integration_id)


@router.get(
    "/api/v1/channel-integrations/{integration_id}/manifest",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def integration_manifest(integration_id: uuid.UUID, request: Request) -> Response:
    media, body, filename = _book(request).manifest(actor(request), integration_id)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/api/v1/channel-integrations/{integration_id}/identities",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def list_identities(integration_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_book(request).identities(actor(request), integration_id))


@router.delete(
    "/api/v1/channel-integrations/{integration_id}/identities/{identity_id}",
    status_code=204,
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def delete_identity(
    integration_id: uuid.UUID, identity_id: uuid.UUID, request: Request
) -> Response:
    _book(request).delete_identity(actor(request), integration_id, identity_id)
    return Response(status_code=204)


@router.get(
    "/api/v1/me/channel-identities",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def my_identities(request: Request) -> dict[str, object]:
    return page(_book(request).my_identities(actor(request)))


@router.post(
    "/api/v1/me/channel-identities:link",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def link_identity(body: LinkBody, request: Request) -> dict[str, object]:
    return _book(request).link(actor(request), body.token)


@router.delete(
    "/api/v1/me/channel-identities/{identity_id}",
    status_code=204,
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def unlink_identity(identity_id: uuid.UUID, request: Request) -> Response:
    _book(request).unlink_mine(actor(request), identity_id)
    return Response(status_code=204)


@router.get(
    "/internal/v1/channels/integrations",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def internal_integrations(request: Request) -> dict[str, object]:
    return {"data": _book(request).integrations_for_channels()}


@router.post(
    "/internal/v1/channels/inbound",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def internal_inbound(body: InboundBody, request: Request) -> dict[str, object]:
    service = chat(request)
    await_runs = bool(getattr(request.app.state, "await_runs", False))
    result = handle_inbound(service, dump(body), schedule=not await_runs)
    run_id = result.get("run_id")
    if await_runs and isinstance(run_id, str) and result.get("action") is None:
        await service.generate(uuid.UUID(run_id), body.text, [])
    return result


@router.post(
    "/internal/v1/channels/approval-decisions",
    dependencies=[Depends(require_permission("channels:manage"))],
)
@expose(public=False, permission="channels:manage")
async def internal_approval(body: ApprovalBody, request: Request) -> dict[str, object]:
    from ar_domain.channels.service import decide_approval  # noqa: PLC0415

    return decide_approval(chat(request), dump(body))

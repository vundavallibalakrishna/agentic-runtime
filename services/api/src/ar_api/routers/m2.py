"""Chat, models, agents, files and runs. Specs 04, 05, 06, 13."""

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import Field
from temporalio.service import RPCError

from ar_api.actors import actor_from
from ar_api.deps import expose, require_permission
from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError, UnavailableError
from ar_common.sandboxkit import download_headers
from ar_contracts.api_model import ApiModel
from ar_domain.agents.access import can_edit
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService
from ar_domain.db.context import Principal
from ar_domain.events.sign import public_json_bytes

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter()


class ProviderBody(ApiModel):
    name: str
    kind: str = "openai_compatible"
    base_url: str
    api_key: str | None = None


class ProviderPatch(ApiModel):
    name: str | None = None


class ModelBody(ApiModel):
    provider_id: uuid.UUID
    name: str
    upstream_model: str
    kind: str = "chat"


class AliasBody(ApiModel):
    alias: str
    kind: str = "chat"
    primary_model_id: uuid.UUID
    fallback_model_ids: list[uuid.UUID] = Field(default_factory=list)


class AliasPatch(ApiModel):
    primary_model_id: uuid.UUID


class AliasTestBody(ApiModel):
    messages: list[dict[str, str]] = Field(default_factory=list)


class ConversationBody(ApiModel):
    agent_id: uuid.UUID | None = None
    agent_version_id: uuid.UUID | None = None
    model_alias: str | None = None


class ConversationPatch(ApiModel):
    title: str | None = None
    pinned: bool | None = None
    model_alias: str | None = None


class MessageBody(ApiModel):
    text: str
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


class EditBody(ApiModel):
    text: str


class FeedbackBody(ApiModel):
    rating: str
    comment: str = ""


class ShareBody(ApiModel):
    principal_type: str
    principal_id: uuid.UUID


class RunBody(ApiModel):
    agent_id: uuid.UUID
    text: str
    callback_url: str | None = None
    on_behalf_of_user_id: uuid.UUID | None = None
    allow_on_behalf_of: bool = False
    wait: bool = False


def _chat(request: Request) -> ChatService:
    service = request.app.state.chat
    if not isinstance(service, ChatService):
        raise NotFoundError()
    return service


def _principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal) or principal.tenant_id is None:
        raise NotFoundError()
    return principal


def _tenant(principal: Principal) -> uuid.UUID:
    tenant_id = principal.tenant_id
    if tenant_id is None:
        raise NotFoundError()
    return tenant_id


def _page(items: list[dict[str, object]]) -> dict[str, object]:
    return {"data": items}


def _platform(principal: Principal) -> None:
    if principal.kind != "platform_admin":
        raise ArError(ErrorCode.FORBIDDEN, "platform admin is required")


async def _finish(
    request: Request, service: ChatService, run_id: str, text: str, names: list[str]
) -> None:
    if getattr(request.app.state, "await_runs", False):
        await service.generate(uuid.UUID(run_id), text, names)


async def _persist_provider(
    service: ChatService,
    created: dict[str, object],
    api_key: str | None,
    principal: Principal,
) -> None:
    from ar_domain.models.registry import save_provider  # noqa: PLC0415

    provider_id = uuid.UUID(str(created["id"]))
    await save_provider(
        service.durable_engine,
        service.providers[provider_id],
        api_key=api_key,
        actor_id=principal.id,
        actor_type=principal.kind,
    )


async def _persist_model(
    service: ChatService, created: dict[str, object], principal: Principal
) -> None:
    from ar_domain.models.registry import save_model  # noqa: PLC0415

    model_id = uuid.UUID(str(created["id"]))
    await save_model(
        service.durable_engine,
        service.models[model_id],
        actor_id=principal.id,
        actor_type=principal.kind,
    )


async def _persist_alias(
    service: ChatService, created: dict[str, object], principal: Principal
) -> None:
    from ar_domain.models.registry import save_alias  # noqa: PLC0415

    alias_id = uuid.UUID(str(created["id"]))
    await save_alias(
        service.durable_engine,
        service.aliases[alias_id],
        actor_id=principal.id,
        actor_type=principal.kind,
    )


@router.get("/api/v1/model-providers", dependencies=[Depends(require_permission("models:read"))])
@expose(public=False, permission="models:read")
async def list_providers(request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(_chat(request).list_providers(_tenant(principal)))


@router.post("/api/v1/model-providers", dependencies=[Depends(require_permission("models:manage"))])
@expose(public=False, permission="models:manage")
async def create_provider(body: ProviderBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    created = service.create_provider(
        _tenant(principal),
        body.name,
        body.kind,
        body.base_url,
        platform=False,
        api_key=body.api_key,
    )
    await _persist_provider(service, created, body.api_key, principal)
    return service._public(service.providers[uuid.UUID(str(created["id"]))])


@router.patch(
    "/api/v1/model-providers/{provider_id}",
    dependencies=[Depends(require_permission("models:manage"))],
)
@expose(public=False, permission="models:manage")
async def patch_provider(
    provider_id: uuid.UUID, body: ProviderPatch, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).update_provider(
        _tenant(principal),
        provider_id,
        platform=False,
        name=body.name,
    )


@router.delete(
    "/api/v1/model-providers/{provider_id}",
    dependencies=[Depends(require_permission("models:manage"))],
)
@expose(public=False, permission="models:manage")
async def delete_provider(provider_id: uuid.UUID, request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _chat(request).delete_provider(_tenant(principal), provider_id, platform=False)
    return {"deleted": True}


@router.post(
    "/api/v1/model-providers/{provider_id}:test",
    dependencies=[Depends(require_permission("models:manage"))],
)
@expose(public=False, permission="models:manage")
async def test_provider(provider_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    return await _chat(request).test_provider(_tenant(principal), provider_id)


@router.get("/api/v1/models", dependencies=[Depends(require_permission("models:read"))])
@expose(public=False, permission="models:read")
async def list_models(request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(_chat(request).list_models(_tenant(principal)))


@router.post("/api/v1/models", dependencies=[Depends(require_permission("models:manage"))])
@expose(public=False, permission="models:manage")
async def create_model(body: ModelBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    created = service.create_model(
        _tenant(principal),
        body.provider_id,
        body.name,
        body.upstream_model,
        body.kind,
        platform=False,
    )
    await _persist_model(service, created, principal)
    return created


@router.delete(
    "/api/v1/models/{model_id}", dependencies=[Depends(require_permission("models:manage"))]
)
@expose(public=False, permission="models:manage")
async def delete_model(model_id: uuid.UUID, request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _chat(request).delete_model(_tenant(principal), model_id, platform=False)
    return {"deleted": True}


@router.get("/api/v1/model-aliases", dependencies=[Depends(require_permission("models:read"))])
@expose(public=False, permission="models:read")
async def list_aliases(request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(_chat(request).list_aliases(_tenant(principal)))


@router.post("/api/v1/model-aliases", dependencies=[Depends(require_permission("models:manage"))])
@expose(public=False, permission="models:manage")
async def create_alias(body: AliasBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    created = service.create_alias(
        _tenant(principal),
        body.alias,
        body.kind,
        body.primary_model_id,
        platform=False,
        fallback_model_ids=body.fallback_model_ids,
    )
    try:
        await _persist_alias(service, created, principal)
    except ConflictError:
        service.aliases.pop(uuid.UUID(str(created["id"])), None)
        raise
    return created


@router.patch(
    "/api/v1/model-aliases/{alias_id}",
    dependencies=[Depends(require_permission("models:manage"))],
)
@expose(public=False, permission="models:manage")
async def update_alias(
    alias_id: uuid.UUID, body: AliasPatch, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    updated = service.update_alias(
        _tenant(principal), alias_id, body.primary_model_id, platform=False
    )
    await _persist_alias(service, updated, principal)
    return updated


@router.post(
    "/api/v1/model-aliases/{alias_id}:test",
    dependencies=[Depends(require_permission("models:manage"))],
)
@expose(public=False, permission="models:manage")
async def test_alias(
    alias_id: uuid.UUID, body: AliasTestBody, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return await _chat(request).test_alias(_tenant(principal), alias_id, body.messages)


@router.get("/api/v1/platform/model-providers")
@expose(public=False, permission=None)
async def platform_providers(request: Request) -> dict[str, object]:
    _platform(_principal(request))
    service = _chat(request)
    return _page([service._public(row) for row in service.providers.values()])


@router.post("/api/v1/platform/model-providers")
@expose(public=False, permission=None)
async def platform_create_provider(body: ProviderBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    _platform(principal)
    service = _chat(request)
    created = service.create_provider(
        None, body.name, body.kind, body.base_url, platform=True, api_key=body.api_key
    )
    await _persist_provider(service, created, body.api_key, principal)
    return service._public(service.providers[uuid.UUID(str(created["id"]))])


@router.get("/api/v1/conversations", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def list_conversations(
    request: Request,
    *,
    include_previews: Annotated[bool, Query(alias="includePreviews")] = False,
) -> dict[str, object]:
    principal = _principal(request)
    return _page(
        _chat(request).list_conversations(
            _tenant(principal),
            uuid.UUID(principal.id),
            include_previews=include_previews,
        )
    )


@router.post("/api/v1/conversations", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def create_conversation(body: ConversationBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    if body.agent_version_id is not None:
        return AgentLifecycle(service).open_preview(actor_from(principal), body.agent_version_id)
    return service.create_conversation(
        _tenant(principal),
        uuid.UUID(principal.id),
        body.agent_id,
        model_alias=body.model_alias,
    )


@router.get(
    "/api/v1/conversations/{conversation_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def get_conversation(conversation_id: uuid.UUID, request: Request) -> dict[str, object]:
    from ar_api.principal import content_hidden  # noqa: PLC0415

    content_hidden(request)
    principal = _principal(request)
    read_all = principal.allows("conversations:read_all")
    service = _chat(request)
    body = service.get_conversation(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        read_all=read_all,
    )
    if body.get("is_preview"):
        agent_id = body.get("agent_id")
        agent = service.agents.get(uuid.UUID(str(agent_id))) if agent_id else None
        if not isinstance(agent, dict) or not can_edit(agent, actor_from(principal)):
            raise NotFoundError()
    return body


@router.patch(
    "/api/v1/conversations/{conversation_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def patch_conversation(
    conversation_id: uuid.UUID, body: ConversationPatch, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    fields = body.model_dump(exclude_unset=True)
    return _chat(request).patch_conversation(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        title=body.title,
        pinned=body.pinned,
        model_alias=body.model_alias,
        model_alias_set="model_alias" in fields,
    )


@router.delete(
    "/api/v1/conversations/{conversation_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def delete_conversation(conversation_id: uuid.UUID, request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _chat(request).delete_conversation(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
    )
    return {"deleted": True}


@router.post(
    "/api/v1/conversations/{conversation_id}/messages",
    status_code=202,
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def post_message(
    conversation_id: uuid.UUID, body: MessageBody, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    await_runs = bool(getattr(request.app.state, "await_runs", False))
    posted = service.post_message(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        body.text,
        attachment_ids=body.attachment_ids,
        schedule=not await_runs,
    )
    run = posted["run"]
    message = posted["message"]
    if await_runs and isinstance(run, dict):
        raw_names = message.get("attachments") if isinstance(message, dict) else None
        names = [str(item) for item in raw_names] if isinstance(raw_names, list) else []
        await _finish(request, service, str(run["id"]), body.text, names)
    return posted


@router.post(
    "/api/v1/conversations/{conversation_id}/messages/{message_id}:regenerate",
    status_code=202,
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def regenerate(
    conversation_id: uuid.UUID, message_id: uuid.UUID, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).regenerate(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        message_id,
    )


@router.post(
    "/api/v1/conversations/{conversation_id}/messages/{message_id}:edit",
    status_code=202,
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def edit_message(
    conversation_id: uuid.UUID, message_id: uuid.UUID, body: EditBody, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).edit_message(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        message_id,
        body.text,
    )


@router.post(
    "/api/v1/conversations/{conversation_id}/messages/{message_id}:activate",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def activate_message(
    conversation_id: uuid.UUID, message_id: uuid.UUID, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).activate_message(_tenant(principal), conversation_id, message_id)


@router.get(
    "/api/v1/conversations/{conversation_id}/messages/{message_id}/grounding",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def message_grounding(
    conversation_id: uuid.UUID, message_id: uuid.UUID, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    message = _chat(request).messages.get(message_id)
    if (
        not isinstance(message, dict)
        or message.get("tenant_id") != _tenant(principal)
        or message.get("conversation_id") != conversation_id
    ):
        raise NotFoundError()
    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "grounding":
                report = part.get("report")
                if isinstance(report, dict):
                    return report
    raise NotFoundError()


@router.put(
    "/api/v1/messages/{message_id}/feedback",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def put_feedback(
    message_id: uuid.UUID, body: FeedbackBody, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).set_feedback(
        _tenant(principal),
        uuid.UUID(principal.id),
        message_id,
        body.rating,
        body.comment,
    )


@router.delete(
    "/api/v1/messages/{message_id}/feedback",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def delete_feedback(message_id: uuid.UUID, request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _chat(request).delete_feedback(_tenant(principal), uuid.UUID(principal.id), message_id)
    return {"deleted": True}


@router.get(
    "/api/v1/conversations/{conversation_id}/shares",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_shares(conversation_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(
        _chat(request).list_shares(_tenant(principal), uuid.UUID(principal.id), conversation_id)
    )


@router.post(
    "/api/v1/conversations/{conversation_id}/shares",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def add_share(
    conversation_id: uuid.UUID, body: ShareBody, request: Request
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).add_share(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        body.principal_type,
        body.principal_id,
    )


@router.delete(
    "/api/v1/conversations/{conversation_id}/shares/{principal_type}/{principal_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def delete_share(
    conversation_id: uuid.UUID, principal_type: str, principal_id: uuid.UUID, request: Request
) -> dict[str, bool]:
    principal = _principal(request)
    _chat(request).delete_share(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        principal_type,
        principal_id,
    )
    return {"deleted": True}


@router.get(
    "/api/v1/conversations/{conversation_id}/export",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def export_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    fmt: Annotated[str, Query(alias="format")] = "markdown",
) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).export_conversation(
        _tenant(principal),
        uuid.UUID(principal.id),
        conversation_id,
        fmt,
    )


@router.post("/api/v1/files:upload", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def upload_file(
    request: Request,
    upload: Annotated[UploadFile, File()],
    mime_type: Annotated[str, Form()] = "",
) -> dict[str, object]:
    principal = _principal(request)
    data = await upload.read()
    mime = mime_type or upload.content_type or "application/octet-stream"
    return _chat(request).upload(
        _tenant(principal),
        uuid.UUID(principal.id),
        upload.filename or "upload",
        mime,
        data,
    )


@router.get("/api/v1/files/{file_id}", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def get_file(file_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).get_file(_tenant(principal), uuid.UUID(principal.id), file_id)


@router.get(
    "/api/v1/files/{file_id}/content", dependencies=[Depends(require_permission("chat:use"))]
)
@expose(public=False, permission="chat:use")
async def file_content(file_id: uuid.UUID, request: Request) -> Response:
    from ar_api.principal import content_hidden  # noqa: PLC0415

    content_hidden(request)
    principal = _principal(request)
    service = _chat(request)
    tenant = _tenant(principal)
    user = uuid.UUID(principal.id)
    row = service.get_file(tenant, user, file_id)
    data, mime = service.file_bytes(tenant, user, file_id)
    headers = download_headers(str(row.get("name") or "download"), mime, inline=True)
    media = headers.get("Content-Type", mime)
    return Response(content=data, media_type=media, headers=headers)


@router.get("/api/v1/files", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def list_files(
    request: Request,
    conversation_id: Annotated[uuid.UUID | None, Query(alias="conversationId")] = None,
) -> dict[str, object]:
    principal = _principal(request)
    return {
        "data": _chat(request).list_files(
            _tenant(principal),
            uuid.UUID(principal.id),
            conversation_id=conversation_id,
        )
    }


@router.delete("/api/v1/files/{file_id}", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def delete_file(file_id: uuid.UUID, request: Request) -> dict[str, bool]:
    principal = _principal(request)
    _chat(request).delete_file(_tenant(principal), uuid.UUID(principal.id), file_id)
    return {"deleted": True}


@router.get("/api/v1/runs", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def list_runs(request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(_chat(request).list_runs(_tenant(principal), uuid.UUID(principal.id)))


@router.post(
    "/api/v1/runs", status_code=202, dependencies=[Depends(require_permission("chat:use"))]
)
@expose(public=False, permission="chat:use")
async def create_run(body: RunBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _chat(request).create_api_run(
        _tenant(principal),
        uuid.UUID(principal.id),
        body.agent_id,
        body.text,
        callback_url=body.callback_url,
        on_behalf_of=body.on_behalf_of_user_id,
        allow_on_behalf=body.allow_on_behalf_of,
    )


@router.get("/api/v1/runs/{run_id}", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def get_run(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    await reload_run(_chat(request), run_id)
    from ar_domain.runs.service import trace_links  # noqa: PLC0415

    return trace_links(_chat(request).get_run(_tenant(principal), run_id))


@router.get("/api/v1/runs/{run_id}/steps", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def list_steps(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(_chat(request).list_steps(_tenant(principal), run_id))


@router.get(
    "/api/v1/runs/{run_id}/tool-calls", dependencies=[Depends(require_permission("chat:use"))]
)
@expose(public=False, permission="chat:use")
async def tool_calls(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    from ar_api.principal import content_hidden  # noqa: PLC0415

    content_hidden(request)
    principal = _principal(request)
    service = _chat(request)
    service.get_run(_tenant(principal), run_id)
    from ar_domain.tools.views import list_calls  # noqa: PLC0415

    return _page(list_calls(service, _tenant(principal), run_id=run_id))


@router.get(
    "/api/v1/runs/{run_id}/children", dependencies=[Depends(require_permission("chat:use"))]
)
@expose(public=False, permission="chat:use")
async def child_runs(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    return _page(_chat(request).list_children(_tenant(principal), run_id))


@router.post("/api/v1/runs/{run_id}:input", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def run_input(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    raw = await request.body()
    text = ""
    if raw:
        import orjson  # noqa: PLC0415

        loaded = orjson.loads(raw)
        if isinstance(loaded, dict):
            text = str(loaded.get("text") or "")
    return _chat(request).submit_input(_tenant(principal), uuid.UUID(principal.id), run_id, text)


@router.post("/api/v1/runs/{run_id}:cancel", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def cancel_run(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = _chat(request)
    run = service.get_run(_tenant(principal), run_id)
    if str(run.get("user_id")) != principal.id:
        raise NotFoundError()
    if run.get("status") in {"completed", "failed", "cancelled"}:
        raise ArError(ErrorCode.INVALID_STATE, "run is not active")
    handle_for = getattr(service.temporal_client, "get_workflow_handle", None)
    if callable(handle_for) and run.get("temporal_workflow_id"):
        try:
            await handle_for(str(run["temporal_workflow_id"])).signal("cancel")
        except RPCError as exc:
            from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

            await reload_run(service, run_id)
            run = service.get_run(_tenant(principal), run_id)
            if run.get("status") not in {"completed", "failed", "cancelled"}:
                raise UnavailableError("The agent could not be stopped. Please try again.") from exc
        return run
    return service.cancel_run(_tenant(principal), uuid.UUID(principal.id), run_id)


@router.get("/api/v1/runs/{run_id}/events", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def run_events(run_id: uuid.UUID, request: Request) -> StreamingResponse:
    principal = _principal(request)
    service = _chat(request)
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    await reload_run(service, run_id)
    service.get_run(_tenant(principal), run_id)
    if not service.acquire_sse(principal.id, 20):
        raise ArError(ErrorCode.RATE_LIMITED, "too many streams")
    header = request.headers.get("last-event-id", "0")
    after = int(header) if header.isdigit() else 0

    async def frames() -> AsyncIterator[bytes]:
        try:
            async for event in service.iter_events(_tenant(principal), run_id, after):
                payload = public_json_bytes(event)
                yield (
                    f"id: {event['seq']}\nevent: {event['type']}\ndata: ".encode()
                    + payload
                    + b"\n\n"
                )
        finally:
            service.release_sse(principal.id)

    return StreamingResponse(frames(), media_type="text/event-stream")

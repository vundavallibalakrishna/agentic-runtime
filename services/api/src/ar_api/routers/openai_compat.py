"""OpenAI-compatible chat facade. Spec: docs/03-specs/16-channels.md §6.

Responses stay snake_case. CamelJsonMiddleware skips `/api/v1/openai/`.
"""

import uuid
from typing import TYPE_CHECKING

import orjson
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import chat
from ar_common.errors import BadRequestError, NotFoundError, ValidationFailedError
from ar_common.wrapping import wrap_untrusted
from ar_contracts.api_model import ApiModel
from ar_domain.agents.logic import AgentView, can_see_agent
from ar_domain.db.context import Principal

if TYPE_CHECKING:
    from collections.abc import Iterator

router = APIRouter()


class ChatPart(ApiModel):
    type: str = "text"
    text: str = ""


class ChatMessage(ApiModel):
    role: str
    content: str | list[ChatPart] | None = None


class ChatRequest(ApiModel):
    model: str
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    user: str | None = None
    tools: list[object] | None = None
    functions: list[object] | None = None


def _principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal) or principal.tenant_id is None:
        raise NotFoundError()
    return principal


def _text(message: ChatMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        return "".join(part.text for part in message.content)
    return ""


def _prompt(body: ChatRequest, *, continued: bool) -> str:
    users = [message for message in body.messages if message.role == "user"]
    if not users:
        raise ValidationFailedError("a user message is required")
    last = _text(users[-1])
    if continued or len(body.messages) <= 1:
        return last
    prior = "\n".join(
        f"{message.role}: {_text(message)}" for message in body.messages if message is not users[-1]
    )
    wrapped = wrap_untrusted(source="prior_messages", content=prior)
    return f"<prior_messages>\n{wrapped}\n</prior_messages>\n\n{last}"


def _channel_open(definition: object) -> bool:
    channels = getattr(definition, "channels", None)
    if channels is None and isinstance(definition, dict):
        channels = definition.get("channels")
    if channels is None:
        return True
    if isinstance(channels, dict):
        return bool(channels.get("api", True))
    return bool(getattr(channels, "api", True))


def _agent(request: Request, slug: str) -> dict[str, object]:
    principal = _principal(request)
    store = chat(request)
    found: dict[str, object] | None = None
    for agent in store.agents.values():
        if agent.get("tenant_id") == principal.tenant_id and agent.get("slug") == slug:
            found = agent
            break
    if found is None:
        raise NotFoundError()
    version_id = found.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    if not _channel_open(definition):
        raise NotFoundError()
    view = AgentView(
        tenant_id=str(found.get("tenant_id")),
        owner_user_id=None
        if found.get("owner_user_id") is None
        else str(found.get("owner_user_id")),
        owner_team_id=None
        if found.get("owner_team_id") is None
        else str(found.get("owner_team_id")),
        visibility=str(found.get("visibility") or "tenant"),
        status=str(found.get("status") or "active"),
        disabled=bool(found.get("disabled")),
    )
    if not can_see_agent(
        view,
        tenant_id=str(principal.tenant_id),
        user_id=principal.id,
        team_ids=set(),
        manage_all=True,
    ):
        raise NotFoundError()
    return found


def _count(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _usage(run: dict[str, object]) -> dict[str, int]:
    raw_usage = run.get("usage")
    raw = raw_usage if isinstance(raw_usage, dict) else {}
    prompt = _count(raw.get("tokens_in"))
    completion = _count(raw.get("tokens_out"))
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _answer(store: object, run_id: uuid.UUID) -> tuple[str, str, dict[str, int]]:
    runs = getattr(store, "runs", {})
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict):
        return "", "stop", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    status = str(run.get("status") or "")
    finish = "approval_required" if status == "waiting_approval" else "stop"
    messages = getattr(store, "messages", {})
    assistant_id = run.get("assistant_message_id")
    text = ""
    if isinstance(messages, dict) and isinstance(assistant_id, uuid.UUID):
        message = messages.get(assistant_id)
        if isinstance(message, dict):
            text = str(message.get("text") or "")
    return text, finish, _usage(run)


def _chunks(text: str, finish: str) -> Iterator[bytes]:
    pieces = [text[index : index + 24] for index in range(0, len(text), 24)] or [""]
    for piece in pieces:
        payload = {
            "id": "chatcmpl-ar",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        yield b"data: " + orjson.dumps(payload) + b"\n\n"
    done = {
        "id": "chatcmpl-ar",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
    }
    if finish == "approval_required":
        done["ar_approval_url"] = "/approvals"
    yield b"data: " + orjson.dumps(done) + b"\n\n"
    yield b"data: [DONE]\n\n"


@router.get("/api/v1/openai/models", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def list_models(request: Request) -> JSONResponse:
    principal = _principal(request)
    store = chat(request)
    data: list[dict[str, str]] = []
    for agent in store.agents.values():
        if agent.get("tenant_id") != principal.tenant_id:
            continue
        if str(agent.get("status") or "") not in {"published", "active"}:
            continue
        version_id = agent.get("published_version_id")
        version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
        definition = version.get("definition") if isinstance(version, dict) else None
        if _channel_open(definition):
            data.append({"id": str(agent.get("slug")), "object": "model", "owned_by": "tenant"})
    return JSONResponse({"object": "list", "data": data})


@router.post(
    "/api/v1/openai/chat/completions",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def chat_completions(body: ChatRequest, request: Request) -> Response:
    if body.tools or body.functions:
        raise BadRequestError("tools are not accepted on this facade")
    del body.user
    principal = _principal(request)
    tenant_id = principal.tenant_id
    if tenant_id is None:
        raise NotFoundError()
    agent = _agent(request, body.model)
    store = chat(request)
    header = request.headers.get("x-ar-conversation-id") or ""
    continued = bool(header)
    if continued:
        conversation_id = uuid.UUID(header)
    else:
        created = store.create_conversation(
            tenant_id, uuid.UUID(principal.id), uuid.UUID(str(agent["id"]))
        )
        conversation_id = uuid.UUID(str(created["id"]))
    stored = store.conversations.get(conversation_id)
    if isinstance(stored, dict):
        stored["channel"] = "api"
    prompt = _prompt(body, continued=continued)
    posted = store.post_message(
        tenant_id,
        uuid.UUID(principal.id),
        conversation_id,
        prompt,
        schedule=False,
    )
    run = posted.get("run") if isinstance(posted, dict) else None
    run_id = uuid.UUID(str(run.get("id"))) if isinstance(run, dict) else None
    if run_id is None:
        raise NotFoundError()
    await store.generate(run_id, prompt, [])
    text, finish, usage = _answer(store, run_id)
    headers = {"X-AR-Run-Id": str(run_id)}
    if body.stream:
        return StreamingResponse(
            _chunks(text, finish), media_type="text/event-stream", headers=headers
        )
    payload: dict[str, object] = {
        "id": "chatcmpl-ar",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": finish,
            }
        ],
        "usage": usage,
    }
    if finish == "approval_required":
        payload["ar_approval_url"] = "/approvals"
    return JSONResponse(payload, headers=headers)

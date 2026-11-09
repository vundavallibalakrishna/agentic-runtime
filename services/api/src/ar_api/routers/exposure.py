"""External agent API, MCP and A2A, plus the key management used by the Expose tab."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated, Any

import orjson
from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import Field

from ar_api.actors import principal_of
from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import chat
from ar_common.errors import ArError, ErrorCode, NotFoundError, UnauthenticatedError
from ar_common.json_api import camelize
from ar_contracts.api_model import ApiModel
from ar_domain.exposure import a2a, keys, mcp_server, runs
from ar_domain.exposure.spec import agent_paths

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

router = APIRouter()

_MESSAGE_EXAMPLE = {
    "id": "4f1c0b2e-6a0d-7e2a-9c3b-1d5e6f708192",
    "conversationId": "8a1b2c3d-4e5f-6789-abcd-ef0123456789",
    "status": "completed",
    "output": "4",
    "finishReason": "stop",
    "usage": {"tokensIn": 12, "tokensOut": 1},
}


class KeyCreate(ApiModel):
    label: str = Field(examples=["Production"])
    scope: str = "agent"
    rate_limit_rpm: int = 60
    monthly_quota: int = 10000


class SendBody(ApiModel):
    text: str = Field(examples=["What is 2 + 2?"])
    stream: bool = False
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


def _store(request: Request) -> Any:
    return chat(request)


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _require_key(request: Request, response: Response) -> dict[str, object]:
    store = _store(request)
    token = _bearer(request)
    row, reason = keys.lookup(store, token)
    if reason == "missing" or row is None:
        keys.audit_key(
            store,
            tenant_id=None,
            actor_id="anonymous",
            action="agent_api_key.denied",
            key_id="",
            label="",
            outcome="failure",
            extra={"reason": "missing"},
        )
        raise UnauthenticatedError("agent api key is required")
    if reason == "revoked":
        keys.audit_key(
            store,
            tenant_id=row.get("tenant_id") if isinstance(row.get("tenant_id"), uuid.UUID) else None,
            actor_id=row.get("created_by_user_id"),
            action="agent_api_key.denied",
            key_id=row.get("id"),
            label=str(row.get("label") or ""),
            outcome="failure",
            extra={"reason": "revoked"},
        )
        raise UnauthenticatedError("agent api key was revoked")
    keys.mark_used(row)
    allowed, limit, remaining = keys.take_rate(store, row)
    response.headers["RateLimit-Limit"] = str(limit)
    response.headers["RateLimit-Remaining"] = str(remaining)
    response.headers["RateLimit-Reset"] = "60"
    request.state.rate_headers = {
        "RateLimit-Limit": str(limit),
        "RateLimit-Remaining": str(remaining),
        "RateLimit-Reset": "60",
    }
    if not allowed:
        keys.audit_key(
            store,
            tenant_id=row.get("tenant_id") if isinstance(row.get("tenant_id"), uuid.UUID) else None,
            actor_id=row.get("created_by_user_id"),
            action="agent_api_call.refused",
            key_id=row.get("id"),
            label=str(row.get("label") or ""),
            outcome="failure",
            extra={"reason": "rate_limit"},
        )
        raise ArError(ErrorCode.RATE_LIMITED, "rate limit exceeded")
    return row


def _agent_row(request: Request, agent_id: uuid.UUID) -> dict[str, object]:
    principal = principal_of(request)
    row = _store(request).agents.get(agent_id)
    if not isinstance(row, dict) or row.get("tenant_id") != principal.tenant_id:
        raise NotFoundError("agent not found")
    return row


def _slug_of(store: Any, key: dict[str, object], slug: str | None) -> str:
    if slug:
        runs.agent_for_key(store, key, slug)
        return slug
    agent = store.agents.get(key.get("agent_id"))
    if not isinstance(agent, dict):
        raise NotFoundError("agent not found")
    return str(agent.get("slug") or "")


def _sse(payload: dict[str, object], event: str = "message") -> bytes:
    data = orjson.dumps(camelize(payload))
    return f"event: {event}\ndata: ".encode() + data + b"\n\n"


def _stream_reply(body: dict[str, object]) -> Iterator[bytes]:
    text = str(body.get("output") or "")
    pieces = [text[index : index + 24] for index in range(0, len(text), 24)] or [""]
    for piece in pieces:
        yield _sse({"text": piece}, "delta")
    yield _sse(body, "done")


@router.get("/v1/openapi.json")
@expose(public=True, permission=None)
async def openapi_document(request: Request) -> JSONResponse:
    """The agent API contract, generated from these routes."""
    return JSONResponse(agent_paths(request.app.openapi()))


@router.get(
    "/api/v1/agents/{agent_id}/exposure",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(public=False, permission="agents:read")
async def get_exposure(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    agent = _agent_row(request, agent_id)
    slug = str(agent.get("slug") or "")
    rows = keys.list_keys(_store(request), agent["tenant_id"], agent_id)  # type: ignore[arg-type]
    return {
        "slug": slug,
        "published": str(agent.get("status") or "") in {"published", "active"},
        "endpoints": _endpoints(slug),
        "keys": [keys.public_key(row) for row in rows],
    }


def _endpoints(slug: str) -> dict[str, str]:
    base = f"/v1/agents/{slug}"
    return {
        "conversations": f"{base}/conversations",
        "messages": f"{base}/conversations/{{conversationId}}/messages",
        "events": f"{base}/runs/{{runId}}/events",
        "trace": f"{base}/runs/{{runId}}",
        "files": f"{base}/files",
        "mcp": "/v1/mcp",
        "agent_card": f"{base}/.well-known/agent-card.json",
        "well_known": "/.well-known/agent-card.json",
        "a2a": f"{base}/a2a",
        "openapi": "/v1/openapi.json",
    }


@router.post(
    "/api/v1/agents/{agent_id}/api-keys",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(public=False, permission="agents:edit")
async def create_agent_key(
    agent_id: uuid.UUID, body: KeyCreate, request: Request
) -> dict[str, object]:
    agent = _agent_row(request, agent_id)
    principal = principal_of(request)
    row, secret = keys.create_key(
        _store(request),
        tenant_id=agent["tenant_id"],  # type: ignore[arg-type]
        agent_id=agent_id,
        user_id=uuid.UUID(principal.id),
        label=body.label,
        scope=body.scope,
        rate_limit_rpm=body.rate_limit_rpm,
        monthly_quota=body.monthly_quota,
    )
    shown = keys.public_key(row)
    shown["key"] = secret
    return shown


@router.post(
    "/api/v1/agents/{agent_id}/api-keys/{key_id}:rotate",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(public=False, permission="agents:edit")
async def rotate_agent_key(
    agent_id: uuid.UUID, key_id: uuid.UUID, request: Request
) -> dict[str, object]:
    agent = _agent_row(request, agent_id)
    principal = principal_of(request)
    row, secret = keys.rotate_key(
        _store(request),
        agent["tenant_id"],  # type: ignore[arg-type]
        agent_id,
        key_id,
        uuid.UUID(principal.id),
    )
    shown = keys.public_key(row)
    shown["key"] = secret
    return shown


@router.delete(
    "/api/v1/agents/{agent_id}/api-keys/{key_id}",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(public=False, permission="agents:edit")
async def revoke_agent_key(
    agent_id: uuid.UUID, key_id: uuid.UUID, request: Request
) -> dict[str, bool]:
    agent = _agent_row(request, agent_id)
    principal = principal_of(request)
    keys.revoke_key(
        _store(request),
        agent["tenant_id"],  # type: ignore[arg-type]
        agent_id,
        key_id,
        uuid.UUID(principal.id),
    )
    return {"revoked": True}


@router.post("/v1/agents/{slug}/conversations")
@expose(public=True, permission=None)
async def create_external_conversation(
    slug: str, request: Request, response: Response
) -> dict[str, object]:
    key = _require_key(request, response)
    return runs.create_conversation(_store(request), key, slug)


@router.post(
    "/v1/agents/{slug}/conversations/{conversation_id}/messages",
    responses={200: {"content": {"application/json": {"example": _MESSAGE_EXAMPLE}}}},
)
@expose(public=True, permission=None)
async def send_external_message(  # noqa: PLR0917
    slug: str,
    conversation_id: uuid.UUID,
    body: SendBody,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> Response:
    key = _require_key(request, response)
    reply, replayed = await runs.send_message(
        _store(request),
        key,
        slug,
        conversation_id,
        body.text,
        body.attachment_ids,
        idempotency_key.strip(),
    )
    headers = dict(getattr(request.state, "rate_headers", {}))
    if replayed:
        headers["Idempotent-Replayed"] = "true"
    if body.stream:
        return StreamingResponse(
            _stream_reply(reply), media_type="text/event-stream", headers=headers
        )
    return JSONResponse(reply, headers=headers)


@router.post(
    "/v1/agents/{slug}:run",
    responses={200: {"content": {"application/json": {"example": _MESSAGE_EXAMPLE}}}},
)
@expose(public=True, permission=None)
async def run_agent_once(
    slug: str,
    body: SendBody,
    request: Request,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
) -> Response:
    """Stateless one-shot run: create a fresh conversation, run one message, return the reply."""
    key = _require_key(request, response)
    reply, replayed = await runs.run_once(
        _store(request),
        key,
        slug,
        body.text,
        body.attachment_ids,
        idempotency_key.strip(),
    )
    headers = dict(getattr(request.state, "rate_headers", {}))
    if replayed:
        headers["Idempotent-Replayed"] = "true"
    if body.stream:
        return StreamingResponse(
            _stream_reply(reply), media_type="text/event-stream", headers=headers
        )
    return JSONResponse(reply, headers=headers)


@router.post("/v1/agents/{slug}/files")
@expose(public=True, permission=None)
async def upload_external_file(
    slug: str,
    request: Request,
    response: Response,
    upload: Annotated[UploadFile, File()],
    mime_type: Annotated[str, Form()] = "",
) -> dict[str, object]:
    key = _require_key(request, response)
    data = await upload.read()
    mime = mime_type or upload.content_type or "application/octet-stream"
    return runs.upload_file(_store(request), key, slug, upload.filename or "upload", mime, data)


@router.get("/v1/agents/{slug}/runs/{run_id}")
@expose(public=True, permission=None)
async def get_external_trace(
    slug: str, run_id: uuid.UUID, request: Request, response: Response
) -> dict[str, object]:
    key = _require_key(request, response)
    return runs.trace(_store(request), key, slug, run_id)


@router.get("/v1/agents/{slug}/runs/{run_id}/events")
@expose(public=True, permission=None)
async def stream_external_events(
    slug: str, run_id: uuid.UUID, request: Request, response: Response
) -> StreamingResponse:
    key = _require_key(request, response)
    body = runs.trace(_store(request), key, slug, run_id)
    events = body.get("events")

    async def generate() -> AsyncIterator[bytes]:
        if isinstance(events, list):
            for event in events:
                if isinstance(event, dict):
                    yield _sse(event, str(event.get("type") or "message"))

    headers = dict(getattr(request.state, "rate_headers", {}))
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)


def _card(request: Request, response: Response, slug: str | None) -> dict[str, object]:
    key = _require_key(request, response)
    chosen = _slug_of(_store(request), key, slug)
    base = str(request.base_url).rstrip("/")
    return a2a.agent_card(_store(request), key, chosen, base)


@router.get("/v1/agents/{slug}/.well-known/agent-card.json")
@expose(public=True, permission=None)
async def get_agent_card_for_slug(
    slug: str, request: Request, response: Response
) -> dict[str, object]:
    return _card(request, response, slug)


@router.get("/.well-known/agent-card.json")
@expose(public=True, permission=None)
async def get_agent_card(
    request: Request,
    response: Response,
    agent: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    return _card(request, response, agent)


async def _a2a(request: Request, response: Response, slug: str | None) -> Response:
    key = _require_key(request, response)
    chosen = _slug_of(_store(request), key, slug)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ArError(ErrorCode.BAD_REQUEST, "json-rpc body is required")
    result = await a2a.rpc(_store(request), key, chosen, payload)
    method = str(payload.get("method") or "")
    headers = dict(getattr(request.state, "rate_headers", {}))
    if method in {"message/stream", "tasks/sendSubscribe"} and "result" in result:
        task = result["result"] if isinstance(result.get("result"), dict) else {}

        def chunks() -> Iterator[bytes]:
            for event in a2a.stream_events(task):
                yield _sse(event, "task")

        return StreamingResponse(chunks(), media_type="text/event-stream", headers=headers)
    return JSONResponse(result, headers=headers)


@router.post("/v1/agents/{slug}/a2a")
@expose(public=True, permission=None)
async def a2a_for_slug(slug: str, request: Request, response: Response) -> Response:
    return await _a2a(request, response, slug)


@router.post("/v1/a2a")
@expose(public=True, permission=None)
async def a2a_rpc(
    request: Request,
    response: Response,
    agent: Annotated[str | None, Query()] = None,
) -> Response:
    return await _a2a(request, response, agent)


async def _mcp(request: Request, response: Response, slug: str | None) -> Response:
    """Streamable HTTP MCP. A JSON body is returned unless the client asks only for SSE."""
    key = _require_key(request, response)
    if slug:
        _slug_of(_store(request), key, slug)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise ArError(ErrorCode.BAD_REQUEST, "json-rpc body is required")
    result = await mcp_server.handle_rpc(_store(request), key, payload)
    headers = dict(getattr(request.state, "rate_headers", {}))
    headers["Mcp-Session-Id"] = str(key.get("id"))
    if result is None:
        return Response(status_code=202, headers=headers)
    accept = request.headers.get("accept") or ""
    if "text/event-stream" in accept and "application/json" not in accept:
        frame = _sse(result, "message")
        return StreamingResponse(iter([frame]), media_type="text/event-stream", headers=headers)
    return JSONResponse(result, headers=headers)


@router.post("/v1/agents/{slug}/mcp")
@expose(public=True, permission=None)
async def mcp_for_slug(slug: str, request: Request, response: Response) -> Response:
    return await _mcp(request, response, slug)


@router.post("/v1/mcp")
@expose(public=True, permission=None)
async def mcp_rpc(request: Request, response: Response) -> Response:
    return await _mcp(request, response, None)

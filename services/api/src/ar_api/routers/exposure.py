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
from ar_common.errors import (
    ArError,
    ErrorCode,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
)
from ar_common.json_api import camelize
from ar_contracts.api_model import ApiModel
from ar_domain.exposure import a2a, keys, mcp_server, runs
from ar_domain.exposure.spec import agent_paths

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

router = APIRouter()


@router.get("/v1")
@expose(public=True, permission=None)
async def public_version() -> dict[str, str]:
    """The versioned public agent API. Additive changes stay on ``/v1``."""
    return {"version": "1"}


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
    response_format: dict[str, object] | None = None
    suggest_followups: bool = False


def _store(request: Request) -> Any:
    return chat(request)


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _require_key(request: Request, response: Response) -> dict[str, object]:
    try:
        store = _store(request)
    except NotFoundError as exc:
        # The read model opens a tenant's rows only for a key that names a tenant. With
        # none open there is no such key, which is a caller without credentials and not a
        # missing resource.
        from ar_common.logging import get_logger  # noqa: PLC0415

        get_logger(__name__).info("agent_api_key_denied", reason="missing")
        raise UnauthenticatedError("agent api key is required") from exc
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
        raise RateLimitedError("rate limit exceeded", retry_after=60)
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


async def _stream_run(
    request: Request,
    key: dict[str, object],
    run_id: uuid.UUID,
    *,
    include_done: bool = True,
) -> AsyncIterator[bytes]:
    """SSE for one run: missed events, heartbeats while it works, then ``done``.

    Resume uses ``Last-Event-ID`` (a sequence or ``{runId}:{seq}``). Events that
    this process did not produce are read from the shared Valkey stream.
    """
    from ar_api.routers.m2 import sse_frame  # noqa: PLC0415
    from ar_domain.runs.event_bus import last_event_seq  # noqa: PLC0415

    store = _store(request)
    tenant = key.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        return
    after = last_event_seq(
        request.headers.get("last-event-id"), request.query_params.get("after_seq")
    )
    last = after
    from ar_domain.exposure.public import include_reasoning, visible_event  # noqa: PLC0415

    show_reasoning = include_reasoning(request.query_params.get("includeReasoning"))
    async for event in store.iter_events(tenant, run_id, after):
        if not visible_event(event, show_reasoning=show_reasoning):
            continue
        seq = event.get("seq")
        if isinstance(seq, int):
            last = max(last, seq)
        yield sse_frame(event)
    if not include_done:
        return
    reply = runs._reply(store, run_id)
    done_seq = last + 1
    yield sse_frame(
        {
            "id": f"{run_id}:{done_seq}",
            "seq": done_seq,
            "type": "done",
            "run_id": str(run_id),
            "data": {"output": reply.get("output"), "status": reply.get("status")},
        }
    )


async def _event_page(
    request: Request, key: dict[str, object], run_id: uuid.UUID
) -> dict[str, object]:
    """One cursor page of a run's events. The cursor is the signed sequence."""
    from ar_common.pagination import decode_cursor, encode_cursor  # noqa: PLC0415
    from ar_common.settings import cursor_secret_text  # noqa: PLC0415

    store = _store(request)
    tenant = key.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        raise NotFoundError("run not found")
    limit_raw = request.query_params.get("limit") or "50"
    limit = int(limit_raw) if limit_raw.isdigit() else 50
    limit = min(max(limit, 1), 200)
    after = 0
    cursor = request.query_params.get("cursor") or ""
    secret = cursor_secret_text()
    if cursor:
        keys, _direction = decode_cursor(cursor, secret=secret)
        if not keys or not isinstance(keys[0], int):
            from ar_common.errors import InvalidCursorError  # noqa: PLC0415

            raise InvalidCursorError()
        after = int(keys[0])
    from ar_domain.exposure.public import include_reasoning, public_events  # noqa: PLC0415

    show_reasoning = include_reasoning(request.query_params.get("includeReasoning"))
    from ar_domain.durable.hydrate import load_run_events  # noqa: PLC0415

    await load_run_events(store, run_id)
    rows = public_events(
        list(store.events_after(tenant, run_id, after)), show_reasoning=show_reasoning
    )
    seen = {event.get("seq") for event in rows}
    extra = await store._bus_replay(run_id, after)
    rows.extend(event for event in extra if event.get("seq") not in seen)
    rows.sort(key=lambda event: int(event["seq"]) if isinstance(event.get("seq"), int) else 0)
    page = rows[:limit]
    has_more = len(rows) > limit
    next_cursor = None
    if has_more and page:
        seq = page[-1].get("seq")
        next_cursor = encode_cursor(
            [seq if isinstance(seq, int) else 0], direction="asc", secret=secret
        )
    return {"items": page, "next_cursor": next_cursor, "has_more": has_more}


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
    from ar_domain.tools.structured import check_response_format  # noqa: PLC0415

    schema = check_response_format(body.response_format)
    reply, replayed = await runs.send_message(
        _store(request),
        key,
        slug,
        conversation_id,
        body.text,
        body.attachment_ids,
        idempotency_key.strip(),
        response_format=schema,
        suggest_followups=body.suggest_followups,
    )
    headers = dict(getattr(request.state, "rate_headers", {}))
    if replayed:
        headers["Idempotent-Replayed"] = "true"
    if body.stream:
        return StreamingResponse(
            _stream_run(request, key, uuid.UUID(str(reply["id"]))),
            media_type="text/event-stream",
            headers=headers,
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
    from ar_domain.tools.structured import check_response_format  # noqa: PLC0415

    schema = check_response_format(body.response_format)
    reply, replayed = await runs.run_once(
        _store(request),
        key,
        slug,
        body.text,
        body.attachment_ids,
        idempotency_key.strip(),
        response_format=schema,
        suggest_followups=body.suggest_followups,
    )
    headers = dict(getattr(request.state, "rate_headers", {}))
    if replayed:
        headers["Idempotent-Replayed"] = "true"
    if body.stream:
        return StreamingResponse(
            _stream_run(request, key, uuid.UUID(str(reply["id"]))),
            media_type="text/event-stream",
            headers=headers,
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
    name = upload.filename or "upload"
    store = _store(request)
    try:
        saved = runs.upload_file(store, key, slug, name, mime, data)
    except ArError:
        raise
    except Exception as exc:
        from ar_common.logging import get_logger  # noqa: PLC0415

        get_logger(__name__).info("agent_file_upload_failed", error=type(exc).__name__)
        raise ArError(ErrorCode.UPSTREAM_ERROR, "The file could not be stored.") from exc
    from ar_api.routers.m2 import _library_document  # noqa: PLC0415
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.exposure.runs import _user_id  # noqa: PLC0415

    tenant_id = key.get("tenant_id")
    if not isinstance(tenant_id, uuid.UUID):
        raise NotFoundError("agent not found")
    document_id = await _library_document(
        store,
        Actor(tenant_id=tenant_id, user_id=_user_id(key), permissions=frozenset()),
        data,
        name,
        mime,
    )
    if document_id:
        saved["document_id"] = document_id
    return saved


@router.get("/v1/agents/{slug}/runs/{run_id}")
@expose(public=True, permission=None)
async def get_external_trace(
    slug: str, run_id: uuid.UUID, request: Request, response: Response
) -> dict[str, object]:
    key = _require_key(request, response)
    from ar_domain.durable.hydrate import load_run_events  # noqa: PLC0415
    from ar_domain.exposure.public import include_reasoning  # noqa: PLC0415

    store = _store(request)
    await load_run_events(store, run_id)
    return runs.trace(
        store,
        key,
        slug,
        run_id,
        show_reasoning=include_reasoning(request.query_params.get("includeReasoning")),
    )


@router.get("/v1/agents/{slug}/runs/{run_id}/events")
@expose(public=True, permission=None)
async def stream_external_events(
    slug: str, run_id: uuid.UUID, request: Request, response: Response
) -> Response:
    """Replay and tail run events. ``Last-Event-ID`` resumes from the shared stream.

    ``Accept: application/json`` returns one cursor page instead of the stream.
    """
    key = _require_key(request, response)
    runs.owned_run(_store(request), key, slug, run_id)
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/event-stream" not in accept:
        return JSONResponse(await _event_page(request, key, run_id))
    headers = dict(getattr(request.state, "rate_headers", {}))
    return StreamingResponse(
        _stream_run(request, key, run_id, include_done=False),
        media_type="text/event-stream",
        headers=headers,
    )


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
    content_type = request.headers.get("content-type", "")
    grpc_method = request.headers.get("x-grpc-method", "")
    if "application/grpc" in content_type or grpc_method:
        from ar_domain.exposure.grpc_a2a import grpc_call  # noqa: PLC0415

        payload = await request.json()
        body = payload if isinstance(payload, dict) else {}
        method = grpc_method or str(body.get("method") or "")
        result, status = await grpc_call(_store(request), key, chosen, method, body)
        headers = dict(getattr(request.state, "rate_headers", {}))
        headers["grpc-status"] = str(status)
        return JSONResponse(result, headers=headers)
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

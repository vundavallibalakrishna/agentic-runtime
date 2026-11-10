"""Research runs, model routes and truncated output. Stage 10."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.m2 import sse_frame
from ar_api.routers.tooling import chat
from ar_common.errors import NotFoundError
from ar_contracts.api_model import ApiModel
from ar_domain.db.context import Principal
from ar_domain.loop.context import public_route, read_output
from ar_domain.loop.routing import replace_routes, routes_for
from ar_domain.research.engine import public_research

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter()


class ResearchBody(ApiModel):
    question: str
    conversation_id: uuid.UUID | None = None
    max_depth: int = Field(default=2, ge=1, le=6)
    max_breadth: int = Field(default=4, ge=1, le=8)
    max_wall_clock_s: int = Field(default=120, ge=1)
    max_cost_micros: int = Field(default=1_000_000, ge=0)


class RouteBody(ApiModel):
    id: str
    base_url: str
    model: str
    secret_name: str = ""


class RoutesBody(ApiModel):
    routes: list[RouteBody] = Field(default_factory=list)


def _principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise NotFoundError()
    return principal


def _owned(request: Request, run_id: uuid.UUID) -> dict[str, object]:
    principal = _principal(request)
    service = chat(request)
    run = service.runs.get(run_id)
    if not isinstance(run, dict) or run.get("tenant_id") != principal.tenant_id:
        raise NotFoundError()
    owner = run.get("user_id")
    if owner is not None and str(owner) != principal.id:
        raise NotFoundError()
    return run


@router.post(
    "/api/v1/research/runs",
    status_code=202,
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def start_research(body: ResearchBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = chat(request)
    tenant = principal.tenant_id
    user = uuid.UUID(principal.id)
    conversation_id = body.conversation_id
    if conversation_id is None:
        created = service.create_conversation(tenant, user, None)
        conversation_id = uuid.UUID(str(created["id"]))
    posted = service.post_message(
        tenant,
        user,
        conversation_id,
        body.question,
        research=True,
        schedule=not bool(getattr(request.app.state, "await_runs", False)),
    )
    run = posted.get("run") if isinstance(posted, dict) else None
    if isinstance(run, dict):
        run["research_bounds"] = {
            "max_depth": body.max_depth,
            "max_breadth": body.max_breadth,
            "max_wall_clock_s": body.max_wall_clock_s,
            "max_cost_micros": body.max_cost_micros,
        }
        checkpoint = run.get("checkpoint")
        if isinstance(checkpoint, dict) and isinstance(checkpoint.get("research"), dict):
            checkpoint["research"].update(run["research_bounds"])
    if getattr(request.app.state, "await_runs", False) and isinstance(run, dict):
        await service.generate(uuid.UUID(str(run["id"])), body.question, [])
    view = public_research(run if isinstance(run, dict) else {})
    view["conversationId"] = str(conversation_id)
    return view


@router.get(
    "/api/v1/research/runs/{run_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def get_research(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    return public_research(_owned(request, run_id))


@router.post(
    "/api/v1/research/runs/{run_id}:cancel",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def cancel_research(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    principal = _principal(request)
    _owned(request, run_id)
    chat(request).cancel_run(principal.tenant_id, uuid.UUID(principal.id), run_id)
    return public_research(_owned(request, run_id))


@router.post(
    "/api/v1/research/runs/{run_id}:resume",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def resume_research(run_id: uuid.UUID, request: Request) -> dict[str, object]:
    _principal(request)
    run = _owned(request, run_id)
    if str(run.get("status") or "") in {"cancelled", "failed", "budget_exceeded"}:
        run["status"] = "running"
        run["ended_at"] = None
        service = chat(request)
        question = ""
        checkpoint = run.get("checkpoint")
        if isinstance(checkpoint, dict) and isinstance(checkpoint.get("research"), dict):
            question = str(checkpoint["research"].get("question") or "")
            if checkpoint["research"].get("phase") == "done":
                checkpoint["research"]["phase"] = "plan"
        run["temporal_workflow_id"] = f"research-{run_id}-resume"
        service._schedule(run_id, question, [])
    return public_research(run)


@router.get(
    "/api/v1/research/runs/{run_id}/events",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def research_events(run_id: uuid.UUID, request: Request) -> StreamingResponse:
    principal = _principal(request)
    _owned(request, run_id)
    service = chat(request)

    async def frames() -> AsyncIterator[bytes]:
        async for event in service.iter_events(principal.tenant_id, run_id, 0):
            yield sse_frame(event)

    return StreamingResponse(frames(), media_type="text/event-stream")


@router.get(
    "/api/v1/runs/{run_id}/outputs/{output_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def read_retained_output(
    run_id: uuid.UUID, output_id: str, request: Request
) -> dict[str, object]:
    run = _owned(request, run_id)
    text = read_output(run, output_id)
    if text is None:
        raise NotFoundError()
    return {"outputId": output_id, "text": text}


@router.get(
    "/api/v1/model-routes",
    dependencies=[Depends(require_permission("models:read"))],
)
@expose(public=False, permission="models:read")
async def list_model_routes(request: Request) -> dict[str, object]:
    principal = _principal(request)
    rows = routes_for(chat(request), principal.tenant_id)
    return {"routes": [public_route(row) for row in rows]}


@router.put(
    "/api/v1/model-routes",
    dependencies=[Depends(require_permission("models:manage"))],
)
@expose(public=False, permission="models:manage")
async def put_model_routes(body: RoutesBody, request: Request) -> dict[str, object]:
    principal = _principal(request)
    service = chat(request)
    saved = [
        {
            "id": item.id,
            "base_url": item.base_url,
            "model": item.model,
            "secret_name": item.secret_name,
        }
        for item in body.routes
    ]
    replace_routes(service, principal.tenant_id, saved)
    return {"routes": [public_route(row) for row in saved]}


def _key_store(request: Request, response: Response) -> tuple[object, dict[str, object]]:
    from ar_api.routers.exposure import _require_key, _store  # noqa: PLC0415

    key = _require_key(request, response)
    return _store(request), key


@router.post("/v1/research/runs", status_code=202)
@expose(public=True, permission=None)
async def start_external_research(
    body: ResearchBody, request: Request, response: Response
) -> dict[str, object]:
    """Start research with an agent API key. The same run streams on the session API."""
    from ar_domain.exposure.runs import create_conversation, send_message  # noqa: PLC0415

    store, key = _key_store(request, response)
    slug = str(request.query_params.get("agent") or "")
    if not slug:
        from ar_domain.exposure.mcp_server import listed_agents  # noqa: PLC0415

        agents = listed_agents(store, key)
        slug = str(agents[0].get("slug") or "") if agents else ""
    created = create_conversation(store, key, slug)
    conversation_id = uuid.UUID(str(created["id"]))
    reply, _replayed = await send_message(
        store, key, slug, conversation_id, body.question, [], "", research=True
    )
    run_id = uuid.UUID(str(reply.get("id")))
    run = store.runs.get(run_id)
    view = public_research(run if isinstance(run, dict) else {})
    view["conversationId"] = str(conversation_id)
    return view


@router.get("/v1/research/runs/{run_id}")
@expose(public=True, permission=None)
async def get_external_research(
    run_id: uuid.UUID, request: Request, response: Response
) -> dict[str, object]:
    store, key = _key_store(request, response)
    run = store.runs.get(run_id)
    if not isinstance(run, dict) or run.get("tenant_id") != key.get("tenant_id"):
        raise NotFoundError()
    return public_research(run)


@router.get("/v1/research/runs/{run_id}/events")
@expose(public=True, permission=None)
async def stream_external_research(
    run_id: uuid.UUID, request: Request, response: Response
) -> StreamingResponse:
    store, key = _key_store(request, response)
    run = store.runs.get(run_id)
    if not isinstance(run, dict) or run.get("tenant_id") != key.get("tenant_id"):
        raise NotFoundError()

    async def frames() -> AsyncIterator[bytes]:
        async for event in store.iter_events(key["tenant_id"], run_id, 0):
            yield sse_frame(event)

    return StreamingResponse(frames(), media_type="text/event-stream")

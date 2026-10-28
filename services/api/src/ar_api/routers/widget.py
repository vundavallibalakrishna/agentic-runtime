"""Embedded chat. Spec: docs/03-specs/16-channels.md §7."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from ar_api.auth.session import SessionData, new_session
from ar_api.auth.widget import (
    active_user,
    agent_ids,
    check_conversation,
    integration,
    record_login,
    widget_session_data,
)
from ar_api.deps import expose, require_permission
from ar_api.routers import m2
from ar_api.routers.tooling import chat
from ar_common.errors import ArError, NotFoundError, UnauthenticatedError
from ar_common.time import utcnow
from ar_contracts.widget import WidgetConversationBody, WidgetMessageBody, WidgetSessionBody
from ar_domain.channels.posts import load_credentials
from ar_domain.channels.widget_auth import allowed_origins, verify_registered_token

router = APIRouter()
WidgetData = Annotated[SessionData, Depends(widget_session_data)]
_CHAT = [Depends(require_permission("chat:use"))]


@router.get("/api/v1/widget/integrations/{integration_id}")
@expose(public=True, permission=None)
async def widget_frame(integration_id: uuid.UUID, request: Request) -> dict[str, object]:
    row = integration(request, integration_id)
    return {"allowed_origins": allowed_origins(row.get("config")), "name": row["name"]}


@router.post("/api/v1/widget/sessions", status_code=204)
@expose(public=True, permission=None)
async def widget_session(body: WidgetSessionBody, request: Request) -> Response:
    row = integration(request, body.integration_id)
    credentials = load_credentials(chat(request), row)
    secret = str(credentials.get("widget_secret") or credentials.get("secret") or "")
    config = row.get("config")
    claims = await verify_registered_token(
        body.token,
        secret=secret,
        audience=f"ar-widget:{body.integration_id}",
        config=config if isinstance(config, dict) else {},
    )
    if claims is None:
        raise UnauthenticatedError()
    tenant_id = uuid.UUID(str(row["tenant_id"]))
    user_id = await active_user(request, tenant_id, claims["sub"])
    if user_id is None:
        raise UnauthenticatedError()
    session_id, data = new_session(tenant_id, user_id)
    data.widget_integration_id = body.integration_id
    data.email = claims["sub"]
    data.display_name = str(claims.get("name") or claims["sub"])
    data.permissions = ["chat:use"]
    ttl = max(1, int(claims["exp"]) - int(utcnow().timestamp()))
    previous = request.cookies.get("ar_widget_session")
    if previous:
        await request.app.state.widget_sessions.delete(previous)
    await record_login(request, data)
    await request.app.state.widget_sessions.put(session_id, data, ttl)
    response = Response(status_code=204, headers={"cache-control": "no-store"})
    response.headers.append(
        "set-cookie",
        (
            f"ar_widget_session={session_id}; HttpOnly; Secure; SameSite=None; "
            f"Partitioned; Path=/api/v1/widget; Max-Age={ttl}"
        ),
    )
    return response


@router.get("/api/v1/widget/session", dependencies=_CHAT)
@expose(public=False, permission="chat:use")
async def widget_context(
    request: Request, response: Response, data: WidgetData
) -> dict[str, object]:
    response.headers["cache-control"] = "no-store"
    row = integration(request, data.widget_integration_id)
    agents = []
    for agent_id in agent_ids(row):
        try:
            agent = chat(request)._pick_agent(data.tenant_id, data.user_id, agent_id)
        except ArError:
            continue
        agents.append({"id": str(agent_id), "name": agent["name"]})
    return {
        "integration_id": data.widget_integration_id,
        "name": row["name"],
        "agents": sorted(agents, key=lambda item: str(item["name"])),
        "csrf_token": data.csrf_token,
        "conversation_id": data.widget_conversation_id,
    }


@router.post("/api/v1/widget/conversations", dependencies=_CHAT)
@expose(public=False, permission="chat:use")
async def widget_conversation(
    body: WidgetConversationBody, request: Request, data: WidgetData
) -> dict[str, object]:
    row = integration(request, data.widget_integration_id)
    if body.agent_id not in agent_ids(row):
        raise NotFoundError()
    conversation = chat(request).create_conversation(data.tenant_id, data.user_id, body.agent_id)
    data.widget_conversation_id = uuid.UUID(str(conversation["id"]))
    # Updating the conversation must not extend the original ten-minute session.
    await request.app.state.widget_sessions.update(request.cookies["ar_widget_session"], data)
    return conversation


@router.get("/api/v1/widget/conversations/{conversation_id}", dependencies=_CHAT)
@expose(public=False, permission="chat:use")
async def widget_messages(
    conversation_id: uuid.UUID, request: Request, data: WidgetData
) -> dict[str, object]:
    check_conversation(request, data, conversation_id)
    current = chat(request).conversations[conversation_id]
    if current.get("active_run_id"):
        from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

        await reload_run(chat(request), uuid.UUID(str(current["active_run_id"])))
    return chat(request).get_conversation(
        data.tenant_id, data.user_id, conversation_id, read_all=False
    )


@router.post(
    "/api/v1/widget/conversations/{conversation_id}/messages", status_code=202, dependencies=_CHAT
)
@expose(public=False, permission="chat:use")
async def widget_send(
    conversation_id: uuid.UUID, body: WidgetMessageBody, request: Request, data: WidgetData
) -> dict[str, object]:
    check_conversation(request, data, conversation_id)
    return await m2.post_message(conversation_id, m2.MessageBody(text=body.text), request)


def _check_run(request: Request, data: SessionData, run_id: uuid.UUID) -> None:
    run = chat(request).get_run(data.tenant_id, run_id)
    check_conversation(request, data, uuid.UUID(str(run["conversation_id"])))


@router.get("/api/v1/widget/runs/{run_id}/events", dependencies=_CHAT)
@expose(public=False, permission="chat:use")
async def widget_events(run_id: uuid.UUID, request: Request, data: WidgetData) -> StreamingResponse:
    _check_run(request, data, run_id)
    return await m2.run_events(run_id, request)


@router.post("/api/v1/widget/runs/{run_id}:cancel", dependencies=_CHAT)
@expose(public=False, permission="chat:use")
async def widget_cancel(run_id: uuid.UUID, request: Request, data: WidgetData) -> dict[str, object]:
    _check_run(request, data, run_id)
    return await m2.cancel_run(run_id, request)

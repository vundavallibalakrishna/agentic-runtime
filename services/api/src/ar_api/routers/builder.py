"""Natural-language builder. Spec: docs/03-specs/05-agent-registry.md §11."""

import uuid

from fastapi import APIRouter, Depends, Request

from ar_api.actors import actor_from, chat_of, principal_of
from ar_api.deps import expose, require_permission
from ar_contracts.api_model import ApiModel
from ar_domain.agents.builder import BuilderService

router = APIRouter()


class SessionBody(ApiModel):
    instruction: str


class SessionMessage(ApiModel):
    text: str


class ApplyBody(ApiModel):
    mode: str = "create"
    agent_id: uuid.UUID | None = None


def _builder(request: Request) -> BuilderService:
    return BuilderService(chat_of(request))


@router.post(
    "/api/v1/builder/sessions", dependencies=[Depends(require_permission("agents:create"))]
)
@expose(public=False, permission="agents:create")
async def start_session(body: SessionBody, request: Request) -> dict[str, object]:
    return await _builder(request).start(actor_from(principal_of(request)), body.instruction)


@router.get(
    "/api/v1/builder/sessions/{session_id}",
    dependencies=[Depends(require_permission("agents:create"))],
)
@expose(public=False, permission="agents:create")
async def read_session(session_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _builder(request).read(actor_from(principal_of(request)), session_id)


@router.post(
    "/api/v1/builder/sessions/{session_id}/messages",
    dependencies=[Depends(require_permission("agents:create"))],
)
@expose(public=False, permission="agents:create")
async def session_message(
    session_id: uuid.UUID, body: SessionMessage, request: Request
) -> dict[str, object]:
    return await _builder(request).message(actor_from(principal_of(request)), session_id, body.text)


@router.post(
    "/api/v1/builder/sessions/{session_id}:apply",
    dependencies=[Depends(require_permission("agents:create"))],
)
@expose(public=False, permission="agents:create")
async def apply_session(
    session_id: uuid.UUID, body: ApplyBody, request: Request
) -> dict[str, object]:
    return _builder(request).apply(
        actor_from(principal_of(request)), session_id, mode=body.mode, agent_id=body.agent_id
    )

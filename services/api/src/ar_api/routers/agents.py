"""Agent registry. Spec: docs/03-specs/05-agent-registry.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import Field

from ar_api.actors import actor_from, chat_of, principal_of
from ar_api.deps import expose, require_permission
from ar_common.errors import ArError, ErrorCode
from ar_contracts.api_model import ApiModel
from ar_domain.agents.assist import draft_from_description
from ar_domain.agents.service import AgentLifecycle

router = APIRouter()


class AgentCreate(ApiModel):
    slug: str
    name: str
    description: str = ""
    visibility: str = "private"
    risk_tier: str = "low"
    template: str | None = None
    definition: dict[str, object] | None = None


class AgentPatch(ApiModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None
    owner_team_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    risk_tier: str | None = None


class DraftBody(ApiModel):
    definition: dict[str, object]
    change_note: str = ""


class PublishBody(ApiModel):
    change_note: str = ""
    skip_eval_gate: bool = False


class RollbackBody(ApiModel):
    version: int
    change_note: str = ""


class DuplicateBody(ApiModel):
    slug: str
    name: str


class DisableBody(ApiModel):
    reason: str
    cancel_active: bool = True


class ValidateBody(ApiModel):
    version_ref: str = "draft"


class DescriptionBody(ApiModel):
    description: str = Field(max_length=4000)
    available_only: bool = True


class FavouriteBody(ApiModel):
    agent_id: uuid.UUID
    favourite: bool = True


def _life(request: Request) -> AgentLifecycle:
    return AgentLifecycle(chat_of(request))


def _page(items: list[dict[str, object]]) -> dict[str, object]:
    return {"data": items}


@router.get("/api/v1/agents", dependencies=[Depends(require_permission("agents:read"))])
@expose(public=False, permission="agents:read")
async def list_agents(
    request: Request,
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    visibility: Annotated[str | None, Query()] = None,
    owner: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    actor = actor_from(principal_of(request))
    return _page(
        _life(request).list_agents(actor, q=q, status=status, visibility=visibility, owner=owner)
    )


@router.post("/api/v1/agents", dependencies=[Depends(require_permission("agents:create"))])
@expose(public=False, permission="agents:create")
async def create_agent(body: AgentCreate, request: Request) -> dict[str, object]:
    return _life(request).create(
        actor_from(principal_of(request)),
        slug=body.slug,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
        risk_tier=body.risk_tier,
        template=body.template,
        definition=body.definition,
    )


@router.post(
    "/api/v1/agents:draft-from-description",
    dependencies=[Depends(require_permission("agents:create"))],
)
@expose(public=False, permission="agents:create")
async def draft_agent(body: DescriptionBody, request: Request) -> dict[str, object]:
    del body.available_only
    return await draft_from_description(
        chat_of(request), actor_from(principal_of(request)), body.description
    )


@router.put(
    "/api/v1/me/agent-favourites", dependencies=[Depends(require_permission("agents:read"))]
)
@expose(public=False, permission="agents:read")
async def set_favourite(body: FavouriteBody, request: Request) -> dict[str, object]:
    return _life(request).set_favourite(
        actor_from(principal_of(request)), body.agent_id, favourite=body.favourite
    )


@router.get("/api/v1/agents/{agent_id}", dependencies=[Depends(require_permission("agents:read"))])
@expose(public=False, permission="agents:read")
async def get_agent(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    actor = actor_from(principal_of(request))
    return _life(request).detail(_life(request)._agent(actor, agent_id), actor)


@router.patch(
    "/api/v1/agents/{agent_id}", dependencies=[Depends(require_permission("agents:edit"))]
)
@expose(public=False, permission="agents:edit")
async def patch_agent(
    agent_id: uuid.UUID,
    body: AgentPatch,
    request: Request,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, object]:
    fields = body.model_dump(exclude_unset=True)
    return _life(request).update(
        actor_from(principal_of(request)), agent_id, if_match=if_match, fields=fields
    )


@router.delete(
    "/api/v1/agents/{agent_id}", dependencies=[Depends(require_permission("agents:read"))]
)
@expose(public=False, permission="agents:read")
async def delete_agent(agent_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _life(request).delete(actor_from(principal_of(request)), agent_id)
    return {"deleted": True}


@router.post(
    "/api/v1/agents/{agent_id}:archive",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(public=False, permission="agents:read")
async def archive_agent(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _life(request).archive(actor_from(principal_of(request)), agent_id)


@router.post(
    "/api/v1/agents/{agent_id}:unarchive",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(public=False, permission="agents:read")
async def unarchive_agent(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _life(request).unarchive(actor_from(principal_of(request)), agent_id)


@router.get(
    "/api/v1/agents/{agent_id}/versions",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(public=False, permission="agents:read")
async def list_versions(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _page(_life(request).versions(actor_from(principal_of(request)), agent_id))


@router.get(
    "/api/v1/agents/{agent_id}/versions/{version_ref}",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(public=False, permission="agents:read")
async def get_version(agent_id: uuid.UUID, version_ref: str, request: Request) -> dict[str, object]:
    return _life(request).version(actor_from(principal_of(request)), agent_id, version_ref)


@router.put(
    "/api/v1/agents/{agent_id}/versions/draft",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(public=False, permission="agents:edit")
async def save_draft(
    agent_id: uuid.UUID,
    body: DraftBody,
    request: Request,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, object]:
    return _life(request).save_draft(
        actor_from(principal_of(request)),
        agent_id,
        body.definition,
        change_note=body.change_note,
        if_match=if_match,
    )


@router.post(
    "/api/v1/agents/{agent_id}:validate",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(public=False, permission="agents:edit")
async def validate_agent(
    agent_id: uuid.UUID, request: Request, body: ValidateBody | None = None
) -> dict[str, object]:
    ref = body.version_ref if body is not None else "draft"
    return _life(request).validate(actor_from(principal_of(request)), agent_id, version_ref=ref)


@router.post(
    "/api/v1/agents/{agent_id}:publish",
    dependencies=[Depends(require_permission("agents:publish"))],
)
@expose(public=False, permission="agents:publish")
async def publish_agent(
    agent_id: uuid.UUID,
    request: Request,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    body: PublishBody | None = None,
) -> dict[str, object]:
    note = body.change_note if body is not None else ""
    if body is not None and body.skip_eval_gate:
        actor = actor_from(principal_of(request))
        if not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "skip_eval_gate requires agents:manage_all")
    result = _life(request).publish(
        actor_from(principal_of(request)),
        agent_id,
        change_note=note,
        if_match=if_match,
        skip_eval_gate=bool(body and body.skip_eval_gate),
    )
    if "eval_run_id" in result and "slug" not in result:
        response.status_code = 202
    return result


@router.post(
    "/api/v1/agents/{agent_id}:rollback",
    dependencies=[Depends(require_permission("agents:publish"))],
)
@expose(public=False, permission="agents:publish")
async def rollback_agent(
    agent_id: uuid.UUID, body: RollbackBody, request: Request
) -> dict[str, object]:
    return _life(request).rollback(
        actor_from(principal_of(request)),
        agent_id,
        version=body.version,
        change_note=body.change_note,
    )


@router.post(
    "/api/v1/agents/{agent_id}:duplicate",
    dependencies=[Depends(require_permission("agents:create"))],
)
@expose(public=False, permission="agents:create")
async def duplicate_agent(
    agent_id: uuid.UUID, body: DuplicateBody, request: Request
) -> dict[str, object]:
    return _life(request).duplicate(
        actor_from(principal_of(request)), agent_id, slug=body.slug, name=body.name
    )


@router.post(
    "/api/v1/agents/{agent_id}:disable",
    dependencies=[Depends(require_permission("agents:disable"))],
)
@expose(public=False, permission="agents:disable")
async def disable_agent(
    agent_id: uuid.UUID, body: DisableBody, request: Request
) -> dict[str, object]:
    return _life(request).disable(
        actor_from(principal_of(request)),
        agent_id,
        reason=body.reason,
        cancel_active=body.cancel_active,
    )


@router.post(
    "/api/v1/agents/{agent_id}:enable",
    dependencies=[Depends(require_permission("agents:disable"))],
)
@expose(public=False, permission="agents:disable")
async def enable_agent(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _life(request).enable(actor_from(principal_of(request)), agent_id)


@router.get(
    "/api/v1/agents/{agent_id}/where-used",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(public=False, permission="agents:edit")
async def where_used(agent_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _life(request).where_used(actor_from(principal_of(request)), agent_id)

"""Skills API. Spec: docs/03-specs/14-skills.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.skills.book import SkillBook

router = APIRouter()


class SkillAsset(ApiModel):
    path: str
    file_id: uuid.UUID


class SkillBody(ApiModel):
    slug: str
    name: str
    description: str
    visibility: str = "tenant"
    owner_team_id: uuid.UUID | None = None
    instructions_md: str = ""
    required_tools: list[str] = Field(default_factory=list)
    assets: list[SkillAsset] = Field(default_factory=list)


class SkillPatch(ApiModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None
    owner_team_id: uuid.UUID | None = None
    instructions_md: str | None = None
    required_tools: list[str] | None = None
    assets: list[SkillAsset] | None = None


class SkillPublishBody(ApiModel):
    change_note: str = ""


def _book(request: Request) -> SkillBook:
    return SkillBook(chat(request))


@router.get("/api/v1/skills", dependencies=[Depends(require_permission("skills:read"))])
@expose(public=False, permission="skills:read")
async def list_skills(
    request: Request,
    q: Annotated[str, Query()] = "",
    status: Annotated[str, Query()] = "",
    owner: Annotated[str, Query()] = "",
    team_id: Annotated[uuid.UUID | None, Query()] = None,
) -> dict[str, object]:
    rows = _book(request).list_skills(
        actor(request), query=q, status=status, owner=owner, team_id=team_id
    )
    return page(rows)


@router.post("/api/v1/skills", dependencies=[Depends(require_permission("skills:create"))])
@expose(public=False, permission="skills:create")
async def create_skill(body: SkillBody, request: Request) -> dict[str, object]:
    return _book(request).create(actor(request), dump(body))


@router.get("/api/v1/skills/{skill_id}", dependencies=[Depends(require_permission("skills:read"))])
@expose(public=False, permission="skills:read")
async def get_skill(skill_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).detail(actor(request), skill_id)


@router.patch(
    "/api/v1/skills/{skill_id}", dependencies=[Depends(require_permission("skills:read"))]
)
@expose(public=False, permission="skills:read")
async def patch_skill(skill_id: uuid.UUID, body: SkillPatch, request: Request) -> dict[str, object]:
    return _book(request).patch(actor(request), skill_id, dump(body))


@router.post(
    "/api/v1/skills/{skill_id}:publish",
    dependencies=[Depends(require_permission("skills:read"))],
)
@expose(public=False, permission="skills:read")
async def publish_skill(
    skill_id: uuid.UUID, body: SkillPublishBody, request: Request
) -> dict[str, object]:
    return _book(request).publish(actor(request), skill_id, change_note=body.change_note)


@router.post(
    "/api/v1/skills/{skill_id}:archive",
    dependencies=[Depends(require_permission("skills:read"))],
)
@expose(public=False, permission="skills:read")
async def archive_skill(skill_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).archive(actor(request), skill_id)


@router.get(
    "/api/v1/skills/{skill_id}/versions",
    dependencies=[Depends(require_permission("skills:read"))],
)
@expose(public=False, permission="skills:read")
async def list_versions(skill_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_book(request).versions(actor(request), skill_id))


@router.get(
    "/api/v1/skills/{skill_id}/versions/{version}",
    dependencies=[Depends(require_permission("skills:read"))],
)
@expose(public=False, permission="skills:read")
async def get_version(skill_id: uuid.UUID, version: int, request: Request) -> dict[str, object]:
    return _book(request).version(actor(request), skill_id, version)


@router.get(
    "/api/v1/skills/{skill_id}/where-used",
    dependencies=[Depends(require_permission("skills:read"))],
)
@expose(public=False, permission="skills:read")
async def where_used(skill_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).where_used(actor(request), skill_id)


@router.post(
    "/api/v1/skills/{skill_id}:republish-dependants",
    dependencies=[Depends(require_permission("skills:read"))],
)
@expose(public=False, permission="skills:read")
async def republish_dependants(skill_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).republish_dependants(actor(request), skill_id)

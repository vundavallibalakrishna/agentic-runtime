"""Memory API. Spec: docs/03-specs/11-memory.md §5."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.memory.book import MemoryBook

router = APIRouter()


class MemoryBody(ApiModel):
    content: str
    scope: str = "user"
    agent_id: uuid.UUID | None = None
    category: str | None = None


class MemoryPatch(ApiModel):
    content: str | None = None
    category: str | None = None


class MemorySettingsBody(ApiModel):
    enabled: bool


class AgentMemoryBody(ApiModel):
    content: str
    category: str | None = None


def _book(request: Request) -> MemoryBook:
    return MemoryBook(chat(request))


@router.get("/api/v1/memory", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def list_memory(  # noqa: PLR0917
    request: Request,
    scope: Annotated[str | None, Query()] = None,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    q: Annotated[str, Query()] = "",
    status: Annotated[str, Query()] = "active",
) -> dict[str, object]:
    book = _book(request)
    person = actor(request)
    return {
        "data": book.list_user(
            person, scope=scope, agent_id=agent_id, category=category, query=q, status=status
        ),
        "memory_enabled": book.memory_enabled(person),
        "teams": book.visible_teams(person),
    }


@router.patch("/api/v1/memory/settings", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def patch_memory_settings(body: MemorySettingsBody, request: Request) -> dict[str, object]:
    return _book(request).set_enabled(actor(request), enabled=body.enabled)


@router.post("/api/v1/memory", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def create_memory(body: MemoryBody, request: Request) -> dict[str, object]:
    return _book(request).create_user(actor(request), dump(body))


@router.patch("/api/v1/memory/{fact_id}", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def patch_memory(
    fact_id: uuid.UUID, body: MemoryPatch, request: Request
) -> dict[str, object]:
    return _book(request).patch_user(actor(request), fact_id, dump(body))


@router.delete("/api/v1/memory/{fact_id}", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def delete_memory(fact_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _book(request).delete_user(actor(request), fact_id)
    return {"deleted": True}


@router.delete("/api/v1/memory", dependencies=[Depends(require_permission("chat:use"))])
@expose(public=False, permission="chat:use")
async def forget_memory(
    request: Request,
    agent_id: Annotated[uuid.UUID | None, Query()] = None,
    x_confirm: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    count = _book(request).forget_all(
        actor(request), agent_id=agent_id, confirmed=x_confirm == "delete-all-memory"
    )
    return {"deleted": count}


@router.get(
    "/api/v1/agents/{agent_id}/memory",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_agent_memory(
    agent_id: uuid.UUID,
    request: Request,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    return page(_book(request).list_agent(actor(request), agent_id, status=status))


@router.post(
    "/api/v1/agents/{agent_id}/memory",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def create_agent_memory(
    agent_id: uuid.UUID, body: AgentMemoryBody, request: Request
) -> dict[str, object]:
    return _book(request).create_agent(actor(request), agent_id, dump(body))


@router.post(
    "/api/v1/agents/{agent_id}/memory/{fact_id}:approve",
    dependencies=[Depends(require_permission("memory:manage_agent"))],
)
@expose(public=False, permission="memory:manage_agent")
async def approve_agent_memory(
    agent_id: uuid.UUID, fact_id: uuid.UUID, request: Request
) -> dict[str, object]:
    return _book(request).approve(actor(request), agent_id, fact_id)


@router.post(
    "/api/v1/agents/{agent_id}/memory/{fact_id}:reject",
    dependencies=[Depends(require_permission("memory:manage_agent"))],
)
@expose(public=False, permission="memory:manage_agent")
async def reject_agent_memory(
    agent_id: uuid.UUID, fact_id: uuid.UUID, request: Request
) -> dict[str, bool]:
    _book(request).reject(actor(request), agent_id, fact_id)
    return {"deleted": True}


@router.patch(
    "/api/v1/agents/{agent_id}/memory/{fact_id}",
    dependencies=[Depends(require_permission("memory:manage_agent"))],
)
@expose(public=False, permission="memory:manage_agent")
async def patch_agent_memory(
    agent_id: uuid.UUID, fact_id: uuid.UUID, body: MemoryPatch, request: Request
) -> dict[str, object]:
    return _book(request).patch_agent(actor(request), agent_id, fact_id, dump(body))


@router.delete(
    "/api/v1/agents/{agent_id}/memory/{fact_id}",
    dependencies=[Depends(require_permission("memory:manage_agent"))],
)
@expose(public=False, permission="memory:manage_agent")
async def delete_agent_memory(
    agent_id: uuid.UUID, fact_id: uuid.UUID, request: Request
) -> dict[str, bool]:
    _book(request).delete_agent(actor(request), agent_id, fact_id)
    return {"deleted": True}


@router.get(
    "/api/v1/teams/{team_id}/memory",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def list_team_memory(team_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_book(request).list_team(actor(request), team_id))


@router.post(
    "/api/v1/teams/{team_id}/memory",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def create_team_memory(
    team_id: uuid.UUID, body: AgentMemoryBody, request: Request
) -> dict[str, object]:
    return _book(request).create_team(actor(request), team_id, dump(body))


@router.delete(
    "/api/v1/teams/{team_id}/memory/{fact_id}",
    dependencies=[Depends(require_permission("chat:use"))],
)
@expose(public=False, permission="chat:use")
async def delete_team_memory(
    team_id: uuid.UUID, fact_id: uuid.UUID, request: Request
) -> dict[str, bool]:
    _book(request).delete_team(actor(request), team_id, fact_id)
    return {"deleted": True}

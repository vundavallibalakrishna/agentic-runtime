"""Tool catalogue, test console and call log. Spec: docs/03-specs/08-tool-registry-mcp.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_common.ids import new_id
from ar_contracts.api_model import ApiModel
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.registry import ToolRegistry
from ar_domain.tools.views import list_calls

router = APIRouter()


class ToolReasonBody(ApiModel):
    reason: str = Field(default="", max_length=500)


class TestBody(ApiModel):
    arguments: dict[str, object] = Field(default_factory=dict)
    dry_run: bool = False
    # Run in this conversation's working folder, so one test can read what another wrote.
    conversation_id: uuid.UUID | None = None


@router.get("/api/v1/tools", dependencies=[Depends(require_permission("tools:read"))])
@expose(public=False, permission="tools:read")
async def list_tools(
    request: Request,
    q: Annotated[str | None, Query()] = None,
    server_id: Annotated[uuid.UUID | None, Query()] = None,
    risk_class: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    return page(
        ToolRegistry(chat(request)).list_tools(
            actor(request), q=q, server_id=server_id, risk_class=risk_class
        )
    )


@router.get("/api/v1/tools/{tool_id}", dependencies=[Depends(require_permission("tools:read"))])
@expose(public=False, permission="tools:read")
async def get_tool(tool_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ToolRegistry(chat(request)).get_tool(actor(request), tool_id)


@router.post(
    "/api/v1/tools/{tool_id}:disable",
    dependencies=[Depends(require_permission("tools:disable"))],
)
@expose(public=False, permission="tools:disable")
async def disable_tool(
    tool_id: uuid.UUID, body: ToolReasonBody, request: Request
) -> dict[str, object]:
    return ToolRegistry(chat(request)).set_tool_enabled(
        actor(request), tool_id, enabled=False, reason=body.reason
    )


@router.post(
    "/api/v1/tools/{tool_id}:enable",
    dependencies=[Depends(require_permission("tools:disable"))],
)
@expose(public=False, permission="tools:disable")
async def enable_tool(tool_id: uuid.UUID, request: Request) -> dict[str, object]:
    return ToolRegistry(chat(request)).set_tool_enabled(actor(request), tool_id, enabled=True)


@router.post(
    "/api/v1/tools/{tool_id}:test", dependencies=[Depends(require_permission("tools:create"))]
)
@expose(public=False, permission="tools:create")
async def test_tool(tool_id: uuid.UUID, body: TestBody, request: Request) -> dict[str, object]:
    store = chat(request)
    who = actor(request)
    detail = ToolRegistry(store).get_tool(who, tool_id)
    run_id = new_id()
    # A console test still has to reference a real agent version. A run with no
    # agent is skipped on flush, and the tool-call row then violates the run
    # foreign key and fails every later save in this process.
    agent = _console_agent(store, who.tenant_id)
    if body.conversation_id is not None:
        # Another tenant's or another person's conversation is not found.
        talk = store._conversation(who.tenant_id, who.user_id, body.conversation_id, read_all=False)
        # A test in a conversation runs as that conversation's agent: its computer
        # template and its tool settings, as a turn there would.
        owner = talk.get("agent_id")
        agent = (store.agents.get(owner) if isinstance(owner, uuid.UUID) else None) or agent
    version_id = None if agent is None else agent.get("published_version_id")
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": who.tenant_id,
        "user_id": who.user_id,
        "conversation_id": body.conversation_id,
        "agent_id": None if agent is None else agent.get("id"),
        "trigger": "api",
        "depth": 0,
        "root_run_id": run_id,
        "synthetic": True,
        "status": "completed",
    }
    return ToolPipeline(store).execute(
        {
            "tenant_id": who.tenant_id,
            "user_id": who.user_id,
            "run_id": run_id,
            "agent_id": None if agent is None else agent.get("id"),
            "agent_version_id": version_id if isinstance(version_id, uuid.UUID) else None,
            "synthetic": True,
            "tool_version_id": uuid.UUID(str(detail["tool_version_id"])),
            "arguments": body.arguments,
            "dry_run": body.dry_run,
            "model_call_id": "test",
        }
    )


@router.get("/api/v1/tool-calls", dependencies=[Depends(require_permission("audit:read"))])
@expose(public=False, permission="audit:read")
async def list_tool_calls(
    request: Request,
    run_id: Annotated[uuid.UUID | None, Query()] = None,
    tool_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    who = actor(request)
    return page(
        list_calls(chat(request), who.tenant_id, run_id=run_id, tool_id=tool_id, status=status, q=q)
    )


def _console_agent(store: object, tenant_id: uuid.UUID) -> dict[str, object] | None:
    """An agent this tenant already published, so the console run can be stored."""
    agents = getattr(store, "agents", None)
    if not isinstance(agents, dict):
        return None
    for row in agents.values():
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            continue
        if row.get("published_version_id") or row.get("draft_version_id"):
            return row
    return None

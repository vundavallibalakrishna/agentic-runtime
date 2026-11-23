"""Tool catalogue, test console and call log. Spec: docs/03-specs/08-tool-registry-mcp.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_contracts.api_model import ApiModel
from ar_domain.tools.console import console_request
from ar_domain.tools.gateway_client import run_console_test
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
    return run_console_test(
        store,
        console_request(
            store,
            actor(request),
            tool_id,
            arguments=body.arguments,
            dry_run=body.dry_run,
            conversation_id=body.conversation_id,
        ),
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

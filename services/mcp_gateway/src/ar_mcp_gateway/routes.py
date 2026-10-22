"""Internal tool execution. Spec: docs/05-contracts/internal-apis.md §3."""

import uuid

from fastapi import APIRouter, Request
from pydantic import Field

from ar_contracts.api_model import ApiModel
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.registry import ToolRegistry
from ar_mcp_gateway.pipeline import execute

router = APIRouter()


class ResolveBody(ApiModel):
    agent_version_id: uuid.UUID
    user_id: uuid.UUID
    query: str = ""


class ExecuteBody(ApiModel):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    run_id: uuid.UUID | None = None
    agent_version_id: uuid.UUID | None = None
    tool_version_id: uuid.UUID
    arguments: dict[str, object] = Field(default_factory=dict)
    model_call_id: str = "call"
    dry_run: bool = False
    synthetic: bool = False
    approval_id: uuid.UUID | None = None
    args_hash: str = ""
    agent_id: uuid.UUID | None = None


class DiscoverBody(ApiModel):
    server_id: uuid.UUID
    version_id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID


def _store(request: Request) -> ChatService:
    service = request.app.state.chat
    if not isinstance(service, ChatService):
        raise TypeError("mcp-gateway has no tool store")
    return service


def _actor(tenant_id: uuid.UUID, user_id: uuid.UUID) -> Actor:
    return Actor(tenant_id, user_id, PERMISSION_KEYS)


@router.post("/internal/v1/catalog:resolve")
async def resolve_catalog(body: ResolveBody, request: Request) -> dict[str, object]:
    return ToolPipeline(_store(request)).resolve_catalog(
        agent_version_id=body.agent_version_id, user_id=body.user_id, query=body.query
    )


@router.post("/internal/v1/tool-calls:execute")
async def execute_call(body: ExecuteBody, request: Request) -> dict[str, object]:
    return execute(_store(request), body.model_dump(by_alias=False))


@router.post("/internal/v1/tool-calls:test")
async def test_call(body: ExecuteBody, request: Request) -> dict[str, object]:
    payload = body.model_dump(by_alias=False)
    payload["synthetic"] = True
    payload["dry_run"] = True if body.dry_run else payload.get("dry_run")
    return ToolPipeline(_store(request)).execute(payload)


@router.post("/internal/v1/discover")
async def discover(body: DiscoverBody, request: Request) -> dict[str, object]:
    return ToolRegistry(_store(request)).discover(
        _actor(body.tenant_id, body.user_id), body.server_id, body.version_id
    )

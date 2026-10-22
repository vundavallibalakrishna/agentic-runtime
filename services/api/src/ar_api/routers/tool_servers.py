"""Tool server registry. Spec: docs/03-specs/08-tool-registry-mcp.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.tools.registry import ToolRegistry

router = APIRouter()


class VersionBody(ApiModel):
    version: str = "1.0.0"
    endpoint_url: str | None = None
    auth_mode: str | None = None
    config: dict[str, object] | None = None
    secret_id: uuid.UUID | None = None
    credential_provider_id: uuid.UUID | None = None


class ServerCreate(ApiModel):
    slug: str
    name: str
    description: str = ""
    kind: str = "remote_mcp"
    version: VersionBody


class ServerPatch(ApiModel):
    name: str | None = None
    description: str | None = None
    owner_team_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None


class ToolPatch(ApiModel):
    risk_class: str | None = None
    description_override: str | None = None
    data_classification: str | None = None
    timeout_s: int | None = None
    idempotent: bool | None = None


class NotesBody(ApiModel):
    notes: str = ""


class ReasonBody(ApiModel):
    reason: str = Field(default="", max_length=500)


def _registry(request: Request) -> ToolRegistry:
    return ToolRegistry(chat(request))


@router.get("/api/v1/tool-servers", dependencies=[Depends(require_permission("tools:read"))])
@expose(public=False, permission="tools:read")
async def list_servers(
    request: Request,
    q: Annotated[str | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, object]:
    return page(_registry(request).list_servers(actor(request), q=q, kind=kind, status=status))


@router.post("/api/v1/tool-servers", dependencies=[Depends(require_permission("tools:create"))])
@expose(public=False, permission="tools:create")
async def create_server(body: ServerCreate, request: Request) -> dict[str, object]:
    payload = dump(body)
    version = payload.get("version")
    if isinstance(version, dict):
        payload["version"] = version
    return _registry(request).create_server(actor(request), payload)


@router.get(
    "/api/v1/tool-servers/{server_id}",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def get_server(server_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _registry(request).get_server(actor(request), server_id)


@router.patch(
    "/api/v1/tool-servers/{server_id}",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def patch_server(
    server_id: uuid.UUID, body: ServerPatch, request: Request
) -> dict[str, object]:
    return _registry(request).patch_server(actor(request), server_id, dump(body))


@router.delete(
    "/api/v1/tool-servers/{server_id}",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def delete_server(server_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _registry(request).delete_server(actor(request), server_id)
    return {"deleted": True}


@router.get(
    "/api/v1/tool-servers/{server_id}/versions",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def list_versions(server_id: uuid.UUID, request: Request) -> dict[str, object]:
    return page(_registry(request).list_versions(actor(request), server_id))


@router.post(
    "/api/v1/tool-servers/{server_id}/versions",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def create_version(
    server_id: uuid.UUID, body: VersionBody, request: Request
) -> dict[str, object]:
    return _registry(request).create_version(actor(request), server_id, dump(body))


@router.get(
    "/api/v1/tool-servers/{server_id}/versions/{version_id}",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def get_version(
    server_id: uuid.UUID, version_id: uuid.UUID, request: Request
) -> dict[str, object]:
    return _registry(request).get_version(actor(request), server_id, version_id)


@router.post(
    "/api/v1/tool-servers/{server_id}/versions/{version_id}:discover",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def discover(
    server_id: uuid.UUID, version_id: uuid.UUID, request: Request
) -> dict[str, object]:
    return _registry(request).discover(actor(request), server_id, version_id)


@router.patch(
    "/api/v1/tool-servers/{server_id}/versions/{version_id}/tools/{tool_version_id}",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def patch_tool(
    server_id: uuid.UUID,
    version_id: uuid.UUID,
    tool_version_id: uuid.UUID,
    body: ToolPatch,
    request: Request,
) -> dict[str, object]:
    return _registry(request).patch_tool(
        actor(request), server_id, version_id, tool_version_id, dump(body)
    )


@router.post(
    "/api/v1/tool-servers/{server_id}/versions/{version_id}:submit",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def submit(
    server_id: uuid.UUID, version_id: uuid.UUID, request: Request
) -> dict[str, object]:
    return _registry(request).submit(actor(request), server_id, version_id)


@router.post(
    "/api/v1/tool-servers/{server_id}/versions/{version_id}:approve",
    dependencies=[Depends(require_permission("tools:review"))],
)
@expose(public=False, permission="tools:review")
async def approve(
    server_id: uuid.UUID, version_id: uuid.UUID, body: NotesBody, request: Request
) -> dict[str, object]:
    return _registry(request).approve(actor(request), server_id, version_id, body.notes)


@router.post(
    "/api/v1/tool-servers/{server_id}/versions/{version_id}:reject",
    dependencies=[Depends(require_permission("tools:review"))],
)
@expose(public=False, permission="tools:review")
async def reject(
    server_id: uuid.UUID, version_id: uuid.UUID, body: NotesBody, request: Request
) -> dict[str, object]:
    return _registry(request).reject(actor(request), server_id, version_id, body.notes)


@router.post(
    "/api/v1/tool-servers/{server_id}:deprecate",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def deprecate(server_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _registry(request).set_server_status(actor(request), server_id, "deprecate")


@router.post(
    "/api/v1/tool-servers/{server_id}:disable",
    dependencies=[Depends(require_permission("tools:disable"))],
)
@expose(public=False, permission="tools:disable")
async def disable(server_id: uuid.UUID, body: ReasonBody, request: Request) -> dict[str, object]:
    return _registry(request).set_server_status(actor(request), server_id, "disable", body.reason)


@router.post(
    "/api/v1/tool-servers/{server_id}:enable",
    dependencies=[Depends(require_permission("tools:disable"))],
)
@expose(public=False, permission="tools:disable")
async def enable(server_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _registry(request).set_server_status(actor(request), server_id, "enable")


@router.get(
    "/internal/v1/connectors/{version_id}/config",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def connector_config(version_id: uuid.UUID, request: Request) -> dict[str, object]:
    """Config a connector process may read. Secrets stay out of this body."""
    store = chat(request)
    version = store.tool_server_versions.get(version_id)
    if not isinstance(version, dict):
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError()
    server_key = version.get("tool_server_id")
    server = store.tool_servers.get(server_key) if isinstance(server_key, uuid.UUID) else None
    if not isinstance(server, dict):
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError()
    who = actor(request)
    if server.get("tenant_id") not in {None, who.tenant_id}:
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError()
    return {
        "tool_server_version_id": str(version_id),
        "slug": server.get("slug"),
        "kind": server.get("kind"),
        "endpoint_url": version.get("endpoint_url"),
        "auth_mode": version.get("auth_mode"),
        "config": version.get("config") or {},
    }

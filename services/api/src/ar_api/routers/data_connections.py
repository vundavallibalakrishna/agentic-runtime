"""Data connections. Spec: docs/03-specs/08-tool-registry-mcp.md §3 and §10."""

import uuid

from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.tools.data_connections import DataConnections

router = APIRouter()


class ConnectionBody(ApiModel):
    name: str
    engine: str = "postgres"
    dsn: str = "memory://warehouse"
    identity_mode: str = "service"
    allowlist: dict[str, object] | None = None
    row_limit: int = 1000
    statement_timeout_s: int = 30
    classification: str = "internal"
    schema_notes: str = ""


class ConnectionPatch(ApiModel):
    name: str | None = None
    schema_notes: str | None = None
    classification: str | None = None
    status: str | None = None
    row_limit: int | None = None
    identity_mode: str | None = None
    allowlist: dict[str, object] | None = None


def _book(request: Request) -> DataConnections:
    return DataConnections(chat(request))


@router.get("/api/v1/data-connections", dependencies=[Depends(require_permission("tools:read"))])
@expose(public=False, permission="tools:read")
async def list_connections(request: Request) -> dict[str, object]:
    return page(_book(request).list_items(actor(request)))


@router.post("/api/v1/data-connections", dependencies=[Depends(require_permission("tools:create"))])
@expose(public=False, permission="tools:create")
async def create_connection(body: ConnectionBody, request: Request) -> dict[str, object]:
    return _book(request).create(actor(request), dump(body))


@router.get(
    "/api/v1/data-connections/{connection_id}",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def get_connection(connection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get(actor(request), connection_id)


@router.patch(
    "/api/v1/data-connections/{connection_id}",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def patch_connection(
    connection_id: uuid.UUID, body: ConnectionPatch, request: Request
) -> dict[str, object]:
    return _book(request).patch(actor(request), connection_id, dump(body))


@router.delete(
    "/api/v1/data-connections/{connection_id}",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def delete_connection(connection_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _book(request).delete(actor(request), connection_id)
    return {"deleted": True}


@router.post(
    "/api/v1/data-connections/{connection_id}:test",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def test_connection(connection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).test(actor(request), connection_id)


@router.get(
    "/api/v1/data-connections/{connection_id}/schema",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def connection_schema(connection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).schema(actor(request), connection_id)


class ProbeBody(ApiModel):
    connection_id: uuid.UUID


@router.post(
    "/internal/v1/connections:test",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def internal_test(body: ProbeBody, request: Request) -> dict[str, object]:
    """Probe a saved connection. The DSN is not returned."""
    return _book(request).test(actor(request), body.connection_id)

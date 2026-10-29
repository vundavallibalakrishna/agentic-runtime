"""Named connections for HTTP, MCP and imported APIs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.tools.service_connections import ConnectionBook

router = APIRouter()


class ServiceConnectionBody(ApiModel):
    name: str
    kind: str
    secret: str = ""
    header_name: str = "X-API-Key"
    username: str = ""
    token_url: str = ""
    authorize_url: str = ""
    client_id: str = ""
    scopes: list[str] = Field(default_factory=list)
    probe_url: str = ""
    expires_at: str = ""


class ServiceConnectionPatch(ApiModel):
    header_name: str | None = None
    username: str | None = None
    token_url: str | None = None
    authorize_url: str | None = None
    client_id: str | None = None
    scopes: list[str] | None = None
    probe_url: str | None = None
    expires_at: str | None = None


class RotateBody(ApiModel):
    secret: str


class ConnectionTestBody(ApiModel):
    url: str = ""


def _book(request: Request) -> ConnectionBook:
    return ConnectionBook(chat(request))


@router.get(
    "/api/v1/service-connections",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def list_service_connections(request: Request) -> dict[str, object]:
    return page(_book(request).list_items(actor(request)))


@router.post(
    "/api/v1/service-connections",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def create_service_connection(
    body: ServiceConnectionBody, request: Request
) -> dict[str, object]:
    return _book(request).create(actor(request), dump(body))


@router.get(
    "/api/v1/service-connections/oauth/callback",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def service_oauth_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> dict[str, object]:
    return await _book(request).callback(code, state)


@router.get(
    "/api/v1/service-connections/{connection_id}",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def get_service_connection(connection_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get(actor(request), connection_id)


@router.patch(
    "/api/v1/service-connections/{connection_id}",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def patch_service_connection(
    connection_id: uuid.UUID, body: ServiceConnectionPatch, request: Request
) -> dict[str, object]:
    return _book(request).update(actor(request), connection_id, dump(body))


@router.post(
    "/api/v1/service-connections/{connection_id}:rotate",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def rotate_service_connection(
    connection_id: uuid.UUID, body: RotateBody, request: Request
) -> dict[str, object]:
    return _book(request).rotate(actor(request), connection_id, body.secret)


@router.post(
    "/api/v1/service-connections/{connection_id}:test",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def test_service_connection(
    connection_id: uuid.UUID, body: ConnectionTestBody, request: Request
) -> dict[str, object]:
    return _book(request).test(actor(request), connection_id, body.url)


@router.post(
    "/api/v1/service-connections/{connection_id}:authorize",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def authorize_service_connection(
    connection_id: uuid.UUID, request: Request
) -> dict[str, object]:
    return _book(request).start(actor(request), connection_id)


@router.delete(
    "/api/v1/service-connections/{connection_id}",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def delete_service_connection(connection_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _book(request).revoke(actor(request), connection_id)
    return {"deleted": True}

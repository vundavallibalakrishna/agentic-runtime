"""Connector catalogue. Spec: docs/09-plan/M26-connectors.md."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.connectors.book import ConnectorBook

router = APIRouter()


class ConnectorInstallBody(ApiModel):
    connection_name: str = ""
    name: str = ""
    kind: str = ""
    secret: str = ""
    username: str = ""
    client_id: str = ""
    config: dict[str, object] | None = None


class ConnectorInstallPatch(ApiModel):
    connection_name: str | None = None
    status: str | None = None
    disabled_tools: list[str] | None = None
    config: dict[str, object] | None = None


def _book(request: Request) -> ConnectorBook:
    return ConnectorBook(chat(request))


@router.get("/api/v1/connectors", dependencies=[Depends(require_permission("tools:read"))])
@expose(public=False, permission="tools:read")
async def list_connectors(
    request: Request,
    q: Annotated[str, Query()] = "",
    category: Annotated[str, Query()] = "",
) -> dict[str, object]:
    return page(_book(request).list_items(actor(request), q=q, category=category))


@router.get(
    "/api/v1/connectors/{slug}",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def get_connector(slug: str, request: Request) -> dict[str, object]:
    return _book(request).get(actor(request), slug)


@router.post(
    "/api/v1/connectors/{slug}:install",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def install_connector(
    slug: str, body: ConnectorInstallBody, request: Request
) -> dict[str, object]:
    return _book(request).install(actor(request), slug, dump(body))


@router.get(
    "/api/v1/connector-installs/{install_id}",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def get_install(install_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).get_install(actor(request), install_id)


@router.patch(
    "/api/v1/connector-installs/{install_id}",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def patch_install(
    install_id: uuid.UUID, body: ConnectorInstallPatch, request: Request
) -> dict[str, object]:
    return _book(request).update(actor(request), install_id, dump(body))


@router.delete(
    "/api/v1/connector-installs/{install_id}",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def delete_install(install_id: uuid.UUID, request: Request) -> dict[str, object]:
    _book(request).remove(actor(request), install_id)
    return {"deleted": True}


@router.post(
    "/api/v1/connector-installs/{install_id}:test",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def test_install(install_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).test(actor(request), install_id)

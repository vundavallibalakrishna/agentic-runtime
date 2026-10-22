"""User connections. Spec: docs/03-specs/03-secrets-credentials.md §3."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, page
from ar_domain.tools.credentials import CredentialBook

router = APIRouter()


def _book(request: Request) -> CredentialBook:
    return CredentialBook(chat(request))


@router.get(
    "/api/v1/connections", dependencies=[Depends(require_permission("connections:manage_own"))]
)
@expose(public=False, permission="connections:manage_own")
async def list_connections(request: Request) -> dict[str, object]:
    return page(_book(request).list_connections(actor(request)))


@router.post(
    "/api/v1/connections/{provider_id}:start",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def start_connection(provider_id: uuid.UUID, request: Request) -> dict[str, object]:
    return _book(request).start(actor(request), provider_id)


@router.get(
    "/api/v1/connections/oauth/callback",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def oauth_callback(
    request: Request,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> dict[str, object]:
    return await _book(request).callback(code, state)


@router.delete(
    "/api/v1/connections/{grant_id}",
    dependencies=[Depends(require_permission("connections:manage_own"))],
)
@expose(public=False, permission="connections:manage_own")
async def disconnect(grant_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _book(request).disconnect(actor(request), grant_id)
    return {"deleted": True}

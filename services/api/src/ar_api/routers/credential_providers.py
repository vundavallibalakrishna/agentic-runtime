"""Credential providers. Spec: docs/03-specs/03-secrets-credentials.md §3."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import expose, require_permission
from ar_api.routers.tooling import actor, chat, dump, page
from ar_contracts.api_model import ApiModel
from ar_domain.tools.credentials import CredentialBook

router = APIRouter()


class CredentialProviderBody(ApiModel):
    slug: str
    name: str
    kind: str = "oauth2"
    authorize_url: str | None = None
    token_url: str | None = None
    client_id: str | None = None
    default_scopes: list[str] = Field(default_factory=list)
    token_exchange_audience: str | None = None
    extra: dict[str, object] | None = None


class CredentialProviderPatch(ApiModel):
    name: str | None = None
    authorize_url: str | None = None
    token_url: str | None = None
    client_id: str | None = None
    status: str | None = None
    extra: dict[str, object] | None = None


def _book(request: Request) -> CredentialBook:
    return CredentialBook(chat(request))


@router.get(
    "/api/v1/credential-providers",
    dependencies=[Depends(require_permission("tools:read"))],
)
@expose(public=False, permission="tools:read")
async def list_providers(request: Request) -> dict[str, object]:
    return page(_book(request).list_providers(actor(request)))


@router.post(
    "/api/v1/credential-providers",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def create_provider(body: CredentialProviderBody, request: Request) -> dict[str, object]:
    return _book(request).create_provider(actor(request), dump(body))


@router.patch(
    "/api/v1/credential-providers/{provider_id}",
    dependencies=[Depends(require_permission("tools:create"))],
)
@expose(public=False, permission="tools:create")
async def patch_provider(
    provider_id: uuid.UUID, body: CredentialProviderPatch, request: Request
) -> dict[str, object]:
    return _book(request).patch_provider(actor(request), provider_id, dump(body))


@router.delete(
    "/api/v1/credential-providers/{provider_id}",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def delete_provider(provider_id: uuid.UUID, request: Request) -> dict[str, bool]:
    _book(request).delete_provider(actor(request), provider_id)
    return {"deleted": True}

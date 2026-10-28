"""Secret metadata API. Values are never returned. Spec: docs/03-specs/03-secrets-credentials.md."""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Request

from ar_api.deps import expose, require_permission
from ar_common.errors import NotFoundError
from ar_contracts.api_model import ApiModel

if TYPE_CHECKING:
    from ar_domain.secrets.service import SecretMetadata
router = APIRouter()


class SecretCreate(ApiModel):
    name: str
    kind: str = "generic"
    value: str
    description: str = ""


class SecretRotate(ApiModel):
    value: str


def _out(item: SecretMetadata) -> dict[str, object]:
    return {
        "id": str(item.id),
        "name": item.name,
        "kind": item.kind,
        "version": item.version,
        "description": item.description,
    }


@router.get("/api/v1/secrets", dependencies=[Depends(require_permission("secrets:use"))])
@expose(public=False, permission="secrets:use")
async def list_secrets(request: Request) -> dict[str, object]:
    rows = await request.app.state.secret_api.list()
    return {"data": [_out(row) for row in rows]}


@router.post("/api/v1/secrets", dependencies=[Depends(require_permission("secrets:manage"))])
@expose(public=False, permission="secrets:manage")
async def create_secret(body: SecretCreate, request: Request) -> dict[str, object]:
    created = await request.app.state.secret_api.create(
        body.name, body.kind, body.value, body.description
    )
    _remember(request, body.name, body.value)
    return _out(created)


@router.get(
    "/api/v1/secrets/{secret_id}", dependencies=[Depends(require_permission("secrets:use"))]
)
@expose(public=False, permission="secrets:use")
async def get_secret(secret_id: uuid.UUID, request: Request) -> dict[str, object]:
    found = await request.app.state.secret_api.get(secret_id)
    if found is None:
        raise NotFoundError("secret not found")
    return _out(found)


@router.patch(
    "/api/v1/secrets/{secret_id}", dependencies=[Depends(require_permission("secrets:manage"))]
)
@expose(public=False, permission="secrets:manage")
async def patch_secret(
    secret_id: uuid.UUID, body: SecretCreate, request: Request
) -> dict[str, object]:
    found = await request.app.state.secret_api.update(secret_id, body.description)
    if found is None:
        raise NotFoundError("secret not found")
    return _out(found)


@router.delete(
    "/api/v1/secrets/{secret_id}", dependencies=[Depends(require_permission("secrets:manage"))]
)
@expose(public=False, permission="secrets:manage")
async def delete_secret(secret_id: uuid.UUID, request: Request) -> dict[str, bool]:
    await request.app.state.secret_api.delete(secret_id)
    return {"deleted": True}


@router.post(
    "/api/v1/secrets/{secret_id}:rotate",
    dependencies=[Depends(require_permission("secrets:manage"))],
)
@expose(public=False, permission="secrets:manage")
async def rotate_secret(
    secret_id: uuid.UUID, body: SecretRotate, request: Request
) -> dict[str, object]:
    found = await request.app.state.secret_api.rotate(secret_id, body.value)
    if found is None:
        raise NotFoundError("secret not found")
    _remember(request, found.name, body.value)
    return _out(found)


def _remember(request: Request, name: str, value: str) -> None:
    """Copy a secret onto the chat store by name. The value is not logged."""
    from ar_domain.tools.general import remember_named_secret  # noqa: PLC0415

    principal = getattr(request.state, "principal", None)
    tenant_id = getattr(principal, "tenant_id", None)
    if not isinstance(tenant_id, uuid.UUID):
        return
    remember_named_secret(request.app.state.chat, tenant_id, name, value)

"""Secret metadata API. Values are never returned. Spec: docs/03-specs/03-secrets-credentials.md."""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from ar_api.deps import SecretsDep, expose, require_permission
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
async def list_secrets(secrets: SecretsDep) -> dict[str, object]:
    return {"data": [_out(row) for row in await secrets.list()]}


@router.post("/api/v1/secrets", dependencies=[Depends(require_permission("secrets:manage"))])
@expose(public=False, permission="secrets:manage")
async def create_secret(body: SecretCreate, secrets: SecretsDep) -> dict[str, object]:
    return _out(await secrets.create(body.name, body.kind, body.value, body.description))


@router.get(
    "/api/v1/secrets/{secret_id}", dependencies=[Depends(require_permission("secrets:use"))]
)
@expose(public=False, permission="secrets:use")
async def get_secret(secret_id: uuid.UUID, secrets: SecretsDep) -> dict[str, object]:
    return _out(await secrets.get(secret_id))


@router.patch(
    "/api/v1/secrets/{secret_id}", dependencies=[Depends(require_permission("secrets:manage"))]
)
@expose(public=False, permission="secrets:manage")
async def patch_secret(
    secret_id: uuid.UUID, body: SecretCreate, secrets: SecretsDep
) -> dict[str, object]:
    return _out(await secrets.describe(secret_id, body.description))


@router.delete(
    "/api/v1/secrets/{secret_id}", dependencies=[Depends(require_permission("secrets:manage"))]
)
@expose(public=False, permission="secrets:manage")
async def delete_secret(secret_id: uuid.UUID, secrets: SecretsDep) -> dict[str, bool]:
    await secrets.delete(secret_id)
    return {"deleted": True}


@router.post(
    "/api/v1/secrets/{secret_id}:rotate",
    dependencies=[Depends(require_permission("secrets:manage"))],
)
@expose(public=False, permission="secrets:manage")
async def rotate_secret(
    secret_id: uuid.UUID, body: SecretRotate, secrets: SecretsDep
) -> dict[str, object]:
    return _out(await secrets.rotate(secret_id, body.value))

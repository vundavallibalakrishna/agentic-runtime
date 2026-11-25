"""Read and save schema-checked settings for an agent or a pack."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request

from ar_api.deps import current_principal, expose, require_permission
from ar_api.routers.tooling import chat
from ar_contracts.api_model import ApiModel
from ar_domain.config_docs.book import SettingsBook

router = APIRouter()


class SettingsBody(ApiModel):
    settings_schema: dict[str, Any] | None = None
    document: dict[str, Any]


@router.get(
    "/api/v1/resource-settings/{resource_type}/{resource_id}",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(permission="agents:read", public=False)
async def read_settings(
    resource_type: str, resource_id: str, request: Request
) -> dict[str, object]:
    tenant_id = _tenant(request)
    found = SettingsBook(chat(request)).latest(tenant_id, resource_type, resource_id)
    return _public(found)


@router.get(
    "/api/v1/resource-settings/{resource_type}/{resource_id}/versions",
    dependencies=[Depends(require_permission("agents:read"))],
)
@expose(permission="agents:read", public=False)
async def list_settings_versions(
    resource_type: str, resource_id: str, request: Request
) -> dict[str, object]:
    tenant_id = _tenant(request)
    rows = SettingsBook(chat(request)).versions(tenant_id, resource_type, resource_id)
    return {"data": [_public(row) for row in rows]}


@router.put(
    "/api/v1/resource-settings/{resource_type}/{resource_id}",
    dependencies=[Depends(require_permission("agents:edit"))],
)
@expose(permission="agents:edit", public=False)
async def save_settings(
    resource_type: str, resource_id: str, body: SettingsBody, request: Request
) -> dict[str, object]:
    tenant_id = _tenant(request)
    principal = current_principal(request)
    try:
        user_id = uuid.UUID(str(principal.id))
    except ValueError:
        user_id = None
    book = SettingsBook(chat(request))
    schema = body.settings_schema
    if schema is None:
        current = book.latest(tenant_id, resource_type, resource_id)
        found = current.get("schema")
        schema = found if isinstance(found, dict) else {}
    saved = book.save(tenant_id, user_id, resource_type, resource_id, schema, body.document)
    return _public(saved)


def _public(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row.get("id"),
        "resourceType": row.get("resource_type"),
        "resourceId": row.get("resource_id"),
        "version": row.get("version"),
        "schema": row.get("schema"),
        "document": row.get("document"),
        "createdAt": row.get("created_at"),
    }


def _tenant(request: Request) -> uuid.UUID:
    tenant_id = current_principal(request).tenant_id
    if not isinstance(tenant_id, uuid.UUID):
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError("settings not found")
    return tenant_id

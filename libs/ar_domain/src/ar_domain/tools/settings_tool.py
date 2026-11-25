"""Read the settings document for an agent or a pack. Nothing here writes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError

if TYPE_CHECKING:
    from typing import Any


def dispatch_settings(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name != "read":
        return _error("unknown_tool", f"unknown tool {name}")
    resource_type = str(arguments.get("resourceType") or arguments.get("resource_type") or "agent")
    resource_id = str(
        arguments.get("resourceId")
        or arguments.get("resource_id")
        or arguments.get("_agent_id")
        or ""
    )
    tenant = _uuid(arguments.get("_tenant_id"))
    if tenant is None or not resource_id:
        return _error("validation_failed", "read needs a tenant and a resource id.")
    from ar_domain.config_docs.book import SettingsBook  # noqa: PLC0415

    try:
        found = SettingsBook(store).latest(tenant, resource_type, resource_id)
    except NotFoundError:
        found = {
            "resourceType": resource_type,
            "resourceId": resource_id,
            "document": {},
            "version": 0,
        }
    text = "No settings are saved." if found.get("version") == 0 else "Settings loaded."
    return {"text": text, "structured": found, "is_error": False}


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _error(code: str, text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": code}

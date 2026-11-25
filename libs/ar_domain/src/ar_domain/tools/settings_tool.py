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
    if not _owns(store, tenant, resource_type, resource_id, arguments.get("_agent_id")):
        return _error("not_found", "No settings are saved.")
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


def _owns(
    store: Any, tenant: uuid.UUID, resource_type: str, resource_id: str, agent_raw: object
) -> bool:
    """An agent may read its own settings and the settings of a pack that contains it."""
    agent_id = _uuid(agent_raw)
    if agent_id is None:
        return False
    agents = getattr(store, "agents", {})
    agent = agents.get(agent_id) if isinstance(agents, dict) else None
    if not isinstance(agent, dict) or agent.get("tenant_id") != tenant:
        return False
    slug = str(agent.get("slug") or "")
    if resource_type == "agent":
        return resource_id in {slug, str(agent_id)}
    if resource_type != "pack":
        return False
    return _pack_contains(store, tenant, resource_id, agent_id, slug)


def _pack_contains(
    store: Any, tenant: uuid.UUID, resource_id: str, agent_id: uuid.UUID, slug: str
) -> bool:
    links = getattr(store, "pack_resources", {})
    packs = getattr(store, "packs", {})
    if not isinstance(links, dict):
        return False
    for link in links.values():
        if not isinstance(link, dict) or link.get("tenant_id") != tenant:
            continue
        if str(link.get("resource_id")) != str(agent_id) and str(link.get("slug") or "") != slug:
            continue
        pack = packs.get(link.get("pack_row_id")) if isinstance(packs, dict) else None
        pack_id = str(pack.get("pack_id") or "") if isinstance(pack, dict) else ""
        if resource_id in {pack_id, str(link.get("slug") or "")}:
            return True
    return False


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

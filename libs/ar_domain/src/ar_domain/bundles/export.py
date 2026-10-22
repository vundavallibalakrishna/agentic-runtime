"""Export agents as a bundle. Secrets are never included."""

import uuid
from typing import Any, cast

import yaml
from pydantic import JsonValue

from ar_contracts.definitions import AgentDefinition
from ar_domain.agents.access import Actor, can_see
from ar_domain.agents.service import AgentLifecycle

_SECRET_KEYS = frozenset(
    {"secret", "password", "token", "api_key", "apiKey", "access_key", "private_key"}
)
_BUILT = frozenset(
    {
        "ToolServer",
        "DataConnection",
        "KnowledgeCollection",
        "Skill",
        "Policy",
        "Routine",
        "ModelAlias",
        "SandboxTemplate",
        "ChannelIntegration",
    }
)


def _strip(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _strip(item)
            for key, item in value.items()
            if str(key) not in _SECRET_KEYS and str(key) != "resolved"
        }
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


def _spec(definition: dict[str, object]) -> dict[str, object]:
    cleaned = cast("dict[str, object]", _strip(definition))
    model = AgentDefinition.model_validate(cleaned)
    dumped = model.model_dump(by_alias=True, mode="json")
    dumped.pop("resolved", None)
    return cast("dict[str, object]", dumped)


def export_bundle(
    store: Any,
    actor: Actor,
    *,
    ids: list[uuid.UUID] | None = None,
) -> dict[str, object]:
    """YAML-shaped bundle document. Only agents this caller can see."""
    life = AgentLifecycle(store)
    life.ensure_builtins(actor.tenant_id, actor.user_id)
    resources: list[dict[str, object]] = []
    for agent in store.agents.values():
        if agent.get("tenant_id") != actor.tenant_id:
            continue
        if ids is not None and agent.get("id") not in ids:
            continue
        if not can_see(agent, actor):
            continue
        version_id = agent.get("published_version_id") or agent.get("draft_version_id")
        if not isinstance(version_id, uuid.UUID):
            continue
        definition = store.versions[version_id].get("definition")
        if not isinstance(definition, dict):
            continue
        resources.append(
            {
                "kind": "Agent",
                "metadata": {
                    "slug": agent.get("slug"),
                    "name": agent.get("name"),
                    "description": agent.get("description") or "",
                    "visibility": agent.get("visibility"),
                    "riskTier": agent.get("risk_tier"),
                },
                "spec": _spec(definition),
            }
        )
    for row in store.catalogue.values():
        if row.get("tenant_id") != actor.tenant_id:
            continue
        kind = str(row.get("kind"))
        if kind not in _BUILT:
            continue
        resources.append(
            {
                "kind": kind,
                "metadata": {"slug": row.get("key"), "name": row.get("name") or row.get("key")},
                "spec": _strip(row.get("spec") or {}),
            }
        )
    document: dict[str, object] = {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "Bundle",
        "metadata": {"name": "export"},
        "spec": {"resources": resources},
    }
    store.audit_log.append(
        {
            "action": "bundle.exported",
            "target_type": "bundle",
            "target_id": actor.tenant_id.hex,
            "detail": {"count": len(resources)},
            "outcome": "success",
        }
    )
    return document


def to_yaml(document: dict[str, object]) -> str:
    """Canonical YAML for a bundle document."""
    return str(yaml.safe_dump(cast("JsonValue", document), sort_keys=True, allow_unicode=True))

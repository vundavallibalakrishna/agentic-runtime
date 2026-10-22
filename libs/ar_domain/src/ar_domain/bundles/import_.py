"""Import a bundle. Apply creates drafts and never publishes."""

import uuid
from typing import Any, cast

import yaml
from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode
from ar_domain.agents.access import Actor, can_edit
from ar_domain.agents.logic import definition_hash
from ar_domain.agents.service import AgentLifecycle
from ar_domain.agents.validation import schema_errors
from ar_domain.bundles.diff import classify, resource_hash

_READY = frozenset({"Agent", "Skill"})
_SKIPPED = frozenset(
    {
        "ToolServer",
        "DataConnection",
        "KnowledgeCollection",
        "Policy",
        "Routine",
        "ModelAlias",
        "SandboxTemplate",
        "ChannelIntegration",
    }
)


def parse_bundle(payload: object) -> list[dict[str, object]]:
    """Accept a document, a YAML string, or a bare resource list."""
    loaded = yaml.safe_load(payload) if isinstance(payload, str) else payload
    if isinstance(loaded, dict):
        spec = loaded.get("spec")
        resources = spec.get("resources") if isinstance(spec, dict) else loaded.get("resources")
        if isinstance(resources, list):
            return [item for item in resources if isinstance(item, dict)]
    return []


def _slug(resource: dict[str, object]) -> str:
    metadata = resource.get("metadata")
    if isinstance(metadata, dict):
        for key in ("slug", "name"):
            if isinstance(metadata.get(key), str):
                return str(metadata[key])
    return ""


def _find(store: Any, tenant_id: uuid.UUID, slug: str) -> dict[str, object] | None:
    for agent in store.agents.values():
        if agent.get("tenant_id") == tenant_id and agent.get("slug") == slug:
            return cast("dict[str, object]", agent)
    return None


def _current_hash(store: Any, agent: dict[str, object]) -> str | None:
    version_id = agent.get("draft_version_id") or agent.get("published_version_id")
    if not isinstance(version_id, uuid.UUID):
        return None
    definition = store.versions[version_id].get("definition")
    if not isinstance(definition, dict):
        return None
    cleaned = {key: value for key, value in definition.items() if key != "resolved"}
    return definition_hash(cleaned)


def import_bundle(  # noqa: PLR0912
    store: Any,
    actor: Actor,
    payload: object,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Plan or apply. Kinds without a module are skipped."""
    life = AgentLifecycle(store)
    results: list[dict[str, object]] = []
    for resource in parse_bundle(payload):
        kind = str(resource.get("kind") or "")
        key = _slug(resource)
        if kind in _SKIPPED:
            results.append({"kind": kind, "key": key, "action": "skipped"})
            continue
        if kind == "Skill":
            results.append(_import_skill(store, actor, resource, key, dry_run=dry_run))
            continue
        if kind not in _READY:
            results.append(
                {"kind": kind, "key": key, "action": "error", "errors": [{"msg": "unknown kind"}]}
            )
            continue
        spec = resource.get("spec")
        if not isinstance(spec, dict):
            results.append(
                {
                    "kind": kind,
                    "key": key,
                    "action": "error",
                    "errors": [{"msg": "missing spec"}],
                }
            )
            continue
        normalised, issues = schema_errors(cast("dict[str, object]", spec))
        if normalised is None:
            results.append(
                {
                    "kind": kind,
                    "key": key,
                    "action": "error",
                    "errors": [{"msg": item.msg, "type": item.type} for item in issues],
                }
            )
            continue
        incoming = resource_hash({"spec": normalised})
        existing = _find(store, actor.tenant_id, key)
        action = classify(
            None if existing is None else _current_hash(store, existing),
            incoming,
            dirty=bool(existing.get("dirty")) if existing else False,
        )
        result: dict[str, object] = {"kind": kind, "key": key, "action": action}
        if action == "conflict":
            result["errors"] = [{"msg": "the agent was edited in this tenant"}]
        elif not dry_run and action == "create":
            metadata = (
                resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
            )
            name = str(metadata.get("name") or key) if isinstance(metadata, dict) else key
            created = life.create(actor, slug=key, name=name, definition=normalised)
            result["id"] = created.get("id")
            stored = _find(store, actor.tenant_id, key)
            if stored is not None:
                stored["dirty"] = False
        elif not dry_run and action == "new_version" and existing is not None:
            if not can_edit(existing, actor):
                raise ArError(ErrorCode.FORBIDDEN, "you cannot update this agent")
            saved = life.save_draft(actor, cast("uuid.UUID", existing["id"]), normalised)
            existing["dirty"] = False
            result["id"] = str(existing["id"])
            result["version_id"] = saved.get("id")
        elif existing is not None:
            result["id"] = str(existing["id"])
        results.append(result)
    if not dry_run:
        store.audit_log.append(
            {
                "action": "bundle.imported",
                "target_type": "bundle",
                "target_id": actor.tenant_id.hex,
                "detail": {"count": len(results)},
                "outcome": "success",
            }
        )
    return {"results": results}


def _text(spec: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = spec.get(key)
        if isinstance(value, str):
            return value
    return ""


def _import_skill(
    store: Any,
    actor: Actor,
    resource: dict[str, object],
    key: str,
    *,
    dry_run: bool,
) -> dict[str, object]:
    """Plan or create a skill draft. Publish stays a separate step."""
    from ar_domain.skills.book import SkillBook  # noqa: PLC0415

    spec = resource.get("spec")
    if not isinstance(spec, dict):
        return {"kind": "Skill", "key": key, "action": "error", "errors": [{"msg": "missing spec"}]}
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    slug = str(metadata.get("slug") or key) if isinstance(metadata, dict) else key
    name = str(metadata.get("name") or slug) if isinstance(metadata, dict) else slug
    body = {
        "slug": slug,
        "name": name,
        "description": _text(spec, "description"),
        "visibility": _text(spec, "visibility") or "tenant",
        "instructions_md": _text(spec, "instructions_md", "instructionsMd"),
        "required_tools": spec.get("required_tools") or spec.get("requiredTools") or [],
    }
    existing = None
    for row in getattr(store, "skills", {}).values():
        if (
            isinstance(row, dict)
            and row.get("tenant_id") == actor.tenant_id
            and row.get("slug") == slug
        ):
            existing = row
            break
    action = "unchanged" if existing is not None else "create"
    result: dict[str, object] = {"kind": "Skill", "key": slug, "action": action}
    if existing is not None:
        result["id"] = str(existing.get("id"))
        return result
    if dry_run:
        return result
    created = SkillBook(store).create(actor, body)
    result["id"] = created.get("id")
    return result


def bundle_yaml(document: dict[str, JsonValue]) -> str:
    return str(yaml.safe_dump(document, sort_keys=True, allow_unicode=True))

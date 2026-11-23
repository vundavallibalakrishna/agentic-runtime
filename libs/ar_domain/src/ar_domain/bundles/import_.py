"""Import a bundle. Apply creates drafts and never publishes.

A routine is created paused: nothing a bundle or a pack brings runs on a schedule until
its owner has read it and turned it on.
"""

import uuid
from typing import TYPE_CHECKING, Any, cast

import yaml
from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode
from ar_domain.agents.access import Actor, can_edit
from ar_domain.agents.logic import definition_hash
from ar_domain.agents.service import AgentLifecycle
from ar_domain.agents.validation import schema_errors
from ar_domain.bundles.diff import classify, resource_hash

if TYPE_CHECKING:
    from collections.abc import Mapping

_READY = frozenset({"Agent", "Skill", "Routine"})
_IMPORTED_PAUSED = "imported"
_SKIPPED = frozenset(
    {
        "ToolServer",
        "DataConnection",
        "KnowledgeCollection",
        "Policy",
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


def import_bundle(  # noqa: PLR0912, PLR0915
    store: Any,
    actor: Actor,
    payload: object,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Plan or apply. Kinds without a module are skipped."""
    life = AgentLifecycle(store)
    results: list[dict[str, object]] = []
    # A routine names its agent, so the agents in the same bundle are made first.
    resources = sorted(parse_bundle(payload), key=lambda item: item.get("kind") == "Routine")
    for resource in resources:
        kind = str(resource.get("kind") or "")
        key = _slug(resource)
        if kind == "Routine":
            results.append(_import_routine(store, actor, resource, key, dry_run=dry_run))
            continue
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


def _import_routine(  # noqa: PLR0911
    store: Any,
    actor: Actor,
    resource: dict[str, object],
    key: str,
    *,
    dry_run: bool,
) -> dict[str, object]:
    """Plan or create a routine, paused. A routine of the same name is left as it is."""
    from pydantic import ValidationError  # noqa: PLC0415

    from ar_contracts.definitions import RoutineDefinition  # noqa: PLC0415
    from ar_domain.routines.book import RoutineBook  # noqa: PLC0415

    result: dict[str, object] = {"kind": "Routine", "key": key, "action": "create"}

    def failed(*errors: Mapping[str, object]) -> dict[str, object]:
        return {**result, "action": "error", "errors": list(errors)}

    try:
        spec = RoutineDefinition.model_validate(resource.get("spec"))
    except ValidationError as exc:
        return failed(
            *(
                {"msg": str(item["msg"]), "loc": ".".join(str(part) for part in item["loc"])}
                for item in exc.errors()
            )
        )
    if not key:
        return failed({"msg": "a routine needs metadata.name"})
    for row in getattr(store, "routines", {}).values():
        if (
            isinstance(row, dict)
            and row.get("tenant_id") == actor.tenant_id
            and row.get("name") == key
        ):
            return {**result, "action": "unchanged", "id": str(row.get("id"))}
    agent = _find(store, actor.tenant_id, spec.agent)
    if dry_run:
        # A plan is made before the bundle's own agents exist, so the agent is not checked.
        return result
    if agent is None:
        return failed(
            {"msg": f"the routine names the agent {spec.agent}, which is not in this workspace"}
        )
    trigger = spec.trigger
    body: dict[str, object] = {
        "name": key,
        "description": spec.description,
        "agent_id": agent["id"],
        "instructions": spec.instructions,
        "trigger": {
            "type": trigger.type,
            "cron": trigger.cron,
            "timezone": trigger.timezone,
            "jitter_s": trigger.jitter_s,
            "catchup_window_s": trigger.catchup_window_s,
            **trigger.config,
        },
        "event_filter": spec.event_filter,
        # A bundle cannot approve its own deliveries: each one waits for the owner.
        "delivery": [
            {**target.model_dump(by_alias=False, exclude_none=True), "pre_approved": False}
            for target in spec.delivery
        ]
        or None,
        "budget": spec.budget.model_dump(by_alias=False),
        "max_runs_per_day": spec.max_runs_per_day,
        "concurrency_policy": spec.concurrency_policy,
    }
    try:
        created = RoutineBook(store).create(actor, body, paused_reason=_IMPORTED_PAUSED)
    except ArError as exc:
        return failed({"msg": exc.detail or exc.title})
    return {**result, "id": str(created.get("id"))}


def bundle_yaml(document: dict[str, JsonValue]) -> str:
    return str(yaml.safe_dump(document, sort_keys=True, allow_unicode=True))

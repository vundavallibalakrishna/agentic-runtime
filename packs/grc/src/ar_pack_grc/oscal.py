"""OSCAL catalog import and export. Skeleton catalogues omit statement prose."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_domain.records.memory import bucket
from ar_pack_grc.access import owned, present, record, same_tenant

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor


def load_json(data: bytes) -> dict[str, Any]:
    try:
        parsed = orjson.loads(data)
    except orjson.JSONDecodeError as exc:
        raise ValidationFailedError("OSCAL file is not JSON") from exc
    if not isinstance(parsed, dict):
        raise ValidationFailedError("OSCAL file is not an object")
    return parsed


def catalog_of(document: dict[str, Any]) -> dict[str, Any]:
    catalog = document.get("catalog")
    if isinstance(catalog, dict):
        return catalog
    if "groups" in document or "controls" in document:
        return document
    raise ValidationFailedError("OSCAL catalog is missing")


def _props(metadata: dict[str, Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    props = metadata.get("props")
    if isinstance(props, list):
        for item in props:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                found[str(item["name"])] = str(item["value"])
    return found


def _statement(control: dict[str, Any]) -> str:
    parts = control.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks = [
        str(part["prose"])
        for part in parts
        if isinstance(part, dict) and part.get("name") == "statement" and part.get("prose")
    ]
    return "\n".join(chunks)


def _controls(node: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    controls = node.get("controls")
    if isinstance(controls, list):
        found.extend(item for item in controls if isinstance(item, dict))
    groups = node.get("groups")
    if isinstance(groups, list):
        for group in groups:
            if isinstance(group, dict):
                found.extend(_controls(group))
    return found


def _groups(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    groups = catalog.get("groups")
    if not isinstance(groups, list):
        return []
    return [item for item in groups if isinstance(item, dict)]


def import_catalog(
    store: Any,
    actor: Actor,
    document: dict[str, Any],
    *,
    pack_owned: bool,
    licence: str | None = None,
) -> dict[str, Any]:
    """Create or update a framework, its requirements and its controls."""
    catalog = catalog_of(document)
    raw_meta = catalog.get("metadata")
    metadata: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    props = _props(metadata)
    key = (props.get("key") or str(metadata.get("title") or "framework")).strip().lower()
    name = str(metadata.get("title") or key)
    version = str(metadata.get("version") or "1")
    chosen = licence or props.get("licence") or "free"
    if chosen not in {"free", "skeleton"}:
        raise ValidationFailedError("licence must be free or skeleton")
    framework = _upsert_framework(
        store,
        actor,
        key=key,
        name=name,
        version=version,
        licence=chosen,
        pack_owned=pack_owned,
    )
    created = 0
    updated = 0
    for group in _groups(catalog):
        _upsert_requirement(
            store,
            actor,
            framework_id=framework["id"],
            key=str(group.get("id") or "").lower(),
            title=str(group.get("title") or group.get("id") or ""),
            statement=_statement(group),
        )
    for control in _controls(catalog):
        control_key = str(control.get("id") or "").strip().lower()
        if not control_key:
            continue
        outcome = _upsert_control(
            store,
            actor,
            framework_id=framework["id"],
            key=control_key,
            title=str(control.get("title") or control_key),
            statement=_statement(control),
        )
        if outcome == "created":
            created += 1
        else:
            updated += 1
    record(
        store,
        actor,
        "grc.framework.imported",
        framework["id"],
        {"key": key, "version": version, "licence": chosen},
    )
    return {
        "framework_id": str(framework["id"]),
        "created": created,
        "updated": updated,
        "errors": [],
    }


def export_catalog(
    store: Any, actor: Actor, framework_id: uuid.UUID, *, include_mappings: bool
) -> dict[str, Any]:
    framework = _framework(store, actor, framework_id)
    skeleton = framework["licence"] == "skeleton"
    controls = [
        row
        for row in bucket(store, "grc_controls").values()
        if same_tenant(row, actor.tenant_id) and row.get("framework_id") == framework_id
    ]
    requirements = [
        row
        for row in bucket(store, "grc_requirements").values()
        if same_tenant(row, actor.tenant_id) and row.get("framework_id") == framework_id
    ]
    groups = []
    placed: set[str] = set()
    for requirement in sorted(requirements, key=lambda row: str(row["key"])):
        prefix = str(requirement["key"])
        nested = []
        for row in sorted(controls, key=lambda item: str(item["key"])):
            key = str(row["key"])
            if key == prefix or key.startswith(prefix + ".") or key.startswith(prefix + "-"):
                nested.append(_control_node(row, skeleton=skeleton))
                placed.add(key)
        groups.append({"id": requirement["key"], "title": requirement["title"], "controls": nested})
    loose = [
        _control_node(row, skeleton=skeleton)
        for row in sorted(controls, key=lambda item: str(item["key"]))
        if str(row["key"]) not in placed
    ]
    body: dict[str, Any] = {
        "catalog": {
            "uuid": str(framework["id"]),
            "metadata": {
                "title": framework["name"],
                "version": framework["version"],
                "oscal-version": "1.1.2",
                "props": [
                    {"name": "key", "value": framework["key"]},
                    {"name": "licence", "value": framework["licence"]},
                ],
            },
            "groups": groups,
            "controls": loose,
        }
    }
    if include_mappings:
        body["mapping-collection"] = _mapping_collection(store, actor, controls)
    return body


def import_licensed_text(
    store: Any, actor: Actor, framework_id: uuid.UUID, data: bytes, *, attestation: bool
) -> dict[str, Any]:
    if attestation is not True:
        raise ValidationFailedError("attestation is required")
    framework = _framework(store, actor, framework_id)
    if framework["licence"] == "free":
        raise ValidationFailedError("licence=free")
    pairs = _licensed_pairs(data)
    known = {
        str(row["key"]): row
        for row in bucket(store, "grc_controls").values()
        if same_tenant(row, actor.tenant_id) and row.get("framework_id") == framework_id
    }
    unknown = sorted(key for key in pairs if key not in known)
    if unknown:
        raise ValidationFailedError("unknown keys: " + ", ".join(unknown))
    for key, statement in pairs.items():
        known[key]["statement"] = statement
    record(
        store,
        actor,
        "grc.framework.imported",
        framework_id,
        {"licence_attested": True, "updated": len(pairs)},
    )
    return {"framework_id": str(framework_id), "updated": len(pairs)}


def _licensed_pairs(data: bytes) -> dict[str, str]:
    text = data.decode("utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        parsed = orjson.loads(data)
        rows = parsed if isinstance(parsed, list) else parsed.get("controls", [])
        if not isinstance(rows, list):
            raise ValidationFailedError("licensed text has no controls")
        pairs: dict[str, str] = {}
        for row in rows:
            if isinstance(row, dict) and row.get("key"):
                pairs[str(row["key"]).lower()] = str(row.get("statement") or "")
        return pairs
    pairs = {}
    for line in text.splitlines():
        if not line.strip() or line.lower().startswith("key,"):
            continue
        key, _, statement = line.partition(",")
        if key.strip():
            pairs[key.strip().lower()] = statement.strip()
    if not pairs:
        raise ValidationFailedError("licensed text is empty")
    return pairs


def _control_node(row: dict[str, Any], *, skeleton: bool) -> dict[str, Any]:
    node: dict[str, Any] = {"id": row["key"], "title": row["title"]}
    statement = str(row.get("statement") or "")
    if statement and not skeleton:
        node["parts"] = [{"name": "statement", "prose": statement}]
    return node


def _mapping_collection(store: Any, actor: Actor, controls: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {row["id"] for row in controls}
    mappings = []
    for row in bucket(store, "grc_mappings").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if row.get("from_control_id") not in ids and row.get("to_control_id") not in ids:
            continue
        if row.get("status") != "confirmed":
            continue
        mappings.append(present(row))
    return {"mappings": mappings}


def _framework(store: Any, actor: Actor, framework_id: uuid.UUID) -> dict[str, Any]:
    row = bucket(store, "grc_frameworks").get(framework_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()
    return row


def _upsert_framework(
    store: Any,
    actor: Actor,
    *,
    key: str,
    name: str,
    version: str,
    licence: str,
    pack_owned: bool,
) -> dict[str, Any]:
    for row in owned(store, "grc_frameworks", actor):
        if row.get("key") == key and row.get("version") == version:
            row["name"] = name
            row["licence"] = licence
            row["pack_owned"] = pack_owned or bool(row.get("pack_owned"))
            return row
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "key": key,
        "name": name,
        "version": version,
        "licence": licence,
        "pack_owned": pack_owned,
    }
    bucket(store, "grc_frameworks")[item_id] = row
    return row


def _upsert_requirement(
    store: Any,
    actor: Actor,
    *,
    framework_id: uuid.UUID,
    key: str,
    title: str,
    statement: str,
) -> None:
    if not key:
        return
    for row in bucket(store, "grc_requirements").values():
        if row.get("framework_id") == framework_id and row.get("key") == key:
            row["title"] = title
            if statement:
                row["statement"] = statement
            return
    item_id = new_id()
    bucket(store, "grc_requirements")[item_id] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "framework_id": framework_id,
        "key": key,
        "title": title or key,
        "statement": statement,
    }


def _upsert_control(
    store: Any,
    actor: Actor,
    *,
    framework_id: uuid.UUID,
    key: str,
    title: str,
    statement: str,
) -> str:
    for row in bucket(store, "grc_controls").values():
        if (
            same_tenant(row, actor.tenant_id)
            and row.get("framework_id") == framework_id
            and row.get("key") == key
        ):
            row["title"] = title
            if statement:
                row["statement"] = statement
            return "updated"
    item_id = new_id()
    bucket(store, "grc_controls")[item_id] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "framework_id": framework_id,
        "entity_id": None,
        "key": key,
        "title": title,
        "statement": statement,
        "owner_user_id": None,
    }
    return "created"

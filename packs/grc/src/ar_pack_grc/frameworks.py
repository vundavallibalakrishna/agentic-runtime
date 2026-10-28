"""Frameworks, requirements and controls."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, owned, present, record, same_tenant, snake_body
from ar_pack_grc.oscal import export_catalog, import_catalog, import_licensed_text, load_json

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

SHIPPED_FREE = frozenset({"nist-csf", "nist-800-53", "csa-ccm"})


def list_frameworks(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(query)
    needle = str(body.get("q") or "").lower()
    licence = str(body.get("licence") or "")
    items = []
    for row in owned(store, "grc_frameworks", actor):
        if licence and row.get("licence") != licence:
            continue
        if needle and needle not in str(row["name"]).lower() and needle not in str(row["key"]):
            continue
        item = present(row)
        item["requirement_count"] = _count(store, actor, "grc_requirements", row["id"])
        items.append(item)
    return {"items": items, "next_cursor": None, "has_more": False}


def create_framework(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(payload)
    key = str(body.get("key") or "").strip().lower()
    name = str(body.get("name") or "").strip()
    version = str(body.get("version") or "").strip()
    licence = str(body.get("licence") or "skeleton")
    if not key or not name or not version:
        raise ValidationFailedError("key, name and version are required")
    if licence not in {"free", "skeleton"}:
        raise ValidationFailedError("licence must be free or skeleton")
    if licence == "free" and key not in SHIPPED_FREE:
        raise ValidationFailedError("licence=free is only for catalogues the pack ships")
    for row in owned(store, "grc_frameworks", actor):
        if row.get("key") == key and row.get("version") == version:
            return _summary(store, actor, row)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "key": key,
        "name": name,
        "version": version,
        "licence": licence,
        "pack_owned": False,
    }
    bucket(store, "grc_frameworks")[item_id] = row
    return _summary(store, actor, row)


def get_framework(store: Any, actor: Actor, framework_id: uuid.UUID) -> dict[str, Any]:
    return _summary(store, actor, one(store, "grc_frameworks", actor, framework_id))


def patch_framework(
    store: Any, actor: Actor, framework_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    row = one(store, "grc_frameworks", actor, framework_id)
    if row.get("licence") == "free" and row.get("pack_owned"):
        from ar_pack_grc.access import forbid  # noqa: PLC0415

        forbid("pack_owned")
    body = snake_body(payload)
    if body.get("name"):
        row["name"] = str(body["name"])
    if body.get("version"):
        row["version"] = str(body["version"])
    return _summary(store, actor, row)


def import_oscal(store: Any, actor: Actor, file_id: uuid.UUID) -> dict[str, Any]:
    return import_catalog(
        store,
        actor,
        load_json(_file_bytes(store, actor, file_id)),
        pack_owned=False,
        licence="free",
    )


def export_oscal(
    store: Any, actor: Actor, framework_id: uuid.UUID, *, include_mappings: bool
) -> dict[str, Any]:
    return export_catalog(store, actor, framework_id, include_mappings=include_mappings)


def import_statements(
    store: Any, actor: Actor, framework_id: uuid.UUID, file_id: uuid.UUID, *, attestation: bool
) -> dict[str, Any]:
    return import_licensed_text(
        store,
        actor,
        framework_id,
        _file_bytes(store, actor, file_id),
        attestation=attestation,
    )


def list_requirements(store: Any, actor: Actor, framework_id: uuid.UUID) -> dict[str, Any]:
    one(store, "grc_frameworks", actor, framework_id)
    items = [
        present(row)
        for row in owned(store, "grc_requirements", actor)
        if row.get("framework_id") == framework_id
    ]
    return {"items": items, "next_cursor": None, "has_more": False}


def get_requirement(store: Any, actor: Actor, requirement_id: uuid.UUID) -> dict[str, Any]:
    row = one(store, "grc_requirements", actor, requirement_id)
    prefix = str(row["key"])
    controls = [
        present(control)
        for control in owned(store, "grc_controls", actor)
        if control.get("framework_id") == row.get("framework_id")
        and (
            str(control["key"]) == prefix
            or str(control["key"]).startswith(prefix + ".")
            or str(control["key"]).startswith(prefix + "-")
        )
    ]
    body = present(row)
    body["controls"] = controls
    return body


def list_controls(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(query)
    framework_id = body.get("framework_id")
    needle = str(body.get("q") or "").lower()
    owner = str(body.get("owner_user_id") or "")
    items = []
    for row in owned(store, "grc_controls", actor):
        if framework_id and str(row.get("framework_id")) != str(framework_id):
            continue
        if owner and str(row.get("owner_user_id") or "") != owner:
            continue
        if needle and needle not in str(row["title"]).lower() and needle not in str(row["key"]):
            continue
        if not _entity_visible(store, actor, row.get("entity_id")):
            continue
        items.append(_control_item(store, actor, row))
    return {"items": items, "next_cursor": None, "has_more": False}


def create_control(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(payload)
    key = str(body.get("key") or "").strip()
    title = str(body.get("title") or "").strip()
    if not key or not title:
        raise ValidationFailedError("key and title are required")
    framework_id = _optional_uuid(body.get("framework_id"))
    if framework_id is not None:
        one(store, "grc_frameworks", actor, framework_id)
    entity_id = _optional_uuid(body.get("entity_id"))
    if entity_id is not None:
        one(store, "grc_entities", actor, entity_id)
    owner = _optional_uuid(body.get("owner_user_id"))
    item_id = new_id()
    row: dict[str, Any] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "framework_id": framework_id,
        "entity_id": entity_id,
        "key": key.lower(),
        "title": title,
        "statement": str(body.get("statement") or ""),
        "owner_user_id": owner,
    }
    bucket(store, "grc_controls")[item_id] = row
    return _control_item(store, actor, row)


def get_control(store: Any, actor: Actor, control_id: uuid.UUID) -> dict[str, Any]:
    row = one(store, "grc_controls", actor, control_id)
    if not _entity_visible(store, actor, row.get("entity_id")):
        raise NotFoundError()
    body = _control_item(store, actor, row)
    body["mappings"] = [
        present(mapping)
        for mapping in bucket(store, "grc_mappings").values()
        if same_tenant(mapping, actor.tenant_id)
        and control_id in {mapping.get("from_control_id"), mapping.get("to_control_id")}
    ]
    body["tests"] = [
        present(test)
        for test in bucket(store, "grc_tests").values()
        if same_tenant(test, actor.tenant_id) and test.get("control_id") == control_id
    ]
    body["evidence_link_count"] = sum(
        1
        for link in bucket(store, "grc_evidence_links").values()
        if same_tenant(link, actor.tenant_id) and link.get("control_id") == control_id
    )
    return body


def patch_control(
    store: Any, actor: Actor, control_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    row = one(store, "grc_controls", actor, control_id)
    body = snake_body(payload)
    changed: list[str] = []
    for field in ("title", "statement"):
        if field in body and body[field] is not None:
            row[field] = str(body[field])
            changed.append(field)
    if "owner_user_id" in body:
        row["owner_user_id"] = _optional_uuid(body.get("owner_user_id"))
        changed.append("owner_user_id")
    if "entity_id" in body:
        entity_id = _optional_uuid(body.get("entity_id"))
        if entity_id is not None:
            one(store, "grc_entities", actor, entity_id)
        row["entity_id"] = entity_id
        changed.append("entity_id")
    if changed:
        record(store, actor, "grc.control.updated", control_id, {"fields": changed})
    return get_control(store, actor, control_id)


def _summary(store: Any, actor: Actor, row: dict[str, Any]) -> dict[str, Any]:
    item = present(row)
    item["requirement_count"] = _count(store, actor, "grc_requirements", row["id"])
    item["control_count"] = _count(store, actor, "grc_controls", row["id"])
    return item


def _count(store: Any, actor: Actor, name: str, framework_id: object) -> int:
    return sum(
        1
        for row in bucket(store, name).values()
        if same_tenant(row, actor.tenant_id) and row.get("framework_id") == framework_id
    )


def _control_item(store: Any, actor: Actor, row: dict[str, Any]) -> dict[str, Any]:
    del store, actor
    return present(row)


def _optional_uuid(value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError("id is not a uuid") from exc


def _file_bytes(store: Any, actor: Actor, file_id: uuid.UUID) -> bytes:
    row = store.files.get(file_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()
    data = store.blobs.get(file_id)
    if not isinstance(data, bytes):
        raise NotFoundError()
    return data


def _entity_visible(store: Any, actor: Actor, entity_id: object) -> bool:
    from ar_pack_grc.entities import can_see_entity  # noqa: PLC0415

    return can_see_entity(store, actor, entity_id)

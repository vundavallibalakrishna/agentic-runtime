"""Legal entities inside one tenant. A grant cannot see a sibling."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, present, record, same_tenant, snake_body

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_KINDS = frozenset({"legal_entity", "division", "region"})


def list_entities(store: Any, actor: Actor) -> dict[str, Any]:
    allowed = _scope(store, actor)
    items = []
    for row in bucket(store, "grc_entities").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if allowed is not None and row["id"] not in allowed:
            continue
        items.append(present(row))
    items.sort(key=lambda item: str(item.get("name")))
    return {"items": items, "next_cursor": None, "has_more": False}


def create_entity(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(payload)
    name = str(body.get("name") or "").strip()
    kind = str(body.get("kind") or "")
    if not name or kind not in _KINDS:
        raise ValidationFailedError("name and kind are required")
    parent_id = _parent(store, actor, body.get("parent_id"))
    item_id = new_id()
    if _cycle(store, actor, item_id, parent_id):
        raise ValidationFailedError("entity parent would create a cycle")
    row: dict[str, Any] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "parent_id": parent_id,
        "name": name,
        "kind": kind,
    }
    bucket(store, "grc_entities")[item_id] = row
    record(store, actor, "grc.entity.updated", item_id, {"name": name, "kind": kind})
    return present(row)


def set_parent(
    store: Any, actor: Actor, entity_id: uuid.UUID, parent_id: uuid.UUID | None
) -> dict[str, Any]:
    """Move an entity. A parent that is the entity or its child is rejected."""
    row = one(store, "grc_entities", actor, entity_id)
    if parent_id is not None:
        one(store, "grc_entities", actor, parent_id)
    if _cycle(store, actor, entity_id, parent_id):
        raise ValidationFailedError("entity parent would create a cycle")
    row["parent_id"] = parent_id
    record(
        store,
        actor,
        "grc.entity.updated",
        entity_id,
        {"parent_id": None if parent_id is None else str(parent_id)},
    )
    return present(row)


def posture(store: Any, actor: Actor, entity_id: uuid.UUID) -> dict[str, Any]:
    row = one(store, "grc_entities", actor, entity_id)
    allowed = _scope(store, actor)
    if allowed is not None and row["id"] not in allowed:
        raise NotFoundError()
    tree = _subtree(store, actor, entity_id)
    control_ids = {
        control["id"]
        for control in bucket(store, "grc_controls").values()
        if same_tenant(control, actor.tenant_id) and control.get("entity_id") in tree
    }
    risks = sum(
        1
        for risk in bucket(store, "grc_risks").values()
        if same_tenant(risk, actor.tenant_id)
        and risk.get("entity_id") in tree
        and risk.get("status") != "closed"
    )
    findings = sum(
        1
        for finding in bucket(store, "grc_findings").values()
        if same_tenant(finding, actor.tenant_id)
        and finding.get("status") == "open"
        and finding.get("control_id") in control_ids
    )
    return {
        "entity_id": str(entity_id),
        "control_count": len(control_ids),
        "open_finding_count": findings,
        "risk_count": risks,
    }


def scope_to_entity(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """Limit one principal to an entity and its children. Tests and grants call this."""
    bucket(store, "grc_entity_grants")[(str(tenant_id), str(user_id))] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "entity_id": entity_id,
    }


def can_see_entity(store: Any, actor: Actor, entity_id: object) -> bool:
    if entity_id is None:
        return _scope(store, actor) is None
    allowed = _scope(store, actor)
    return allowed is None or entity_id in allowed


def _scope(store: Any, actor: Actor) -> set[uuid.UUID] | None:
    grant = bucket(store, "grc_entity_grants").get((str(actor.tenant_id), str(actor.user_id)))
    if not isinstance(grant, dict):
        return None
    root = grant.get("entity_id")
    if not isinstance(root, uuid.UUID):
        return None
    return _subtree(store, actor, root)


def _parent(store: Any, actor: Actor, value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        parent_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError("parent id is not a uuid") from exc
    one(store, "grc_entities", actor, parent_id)
    allowed = _scope(store, actor)
    if allowed is not None and parent_id not in allowed:
        raise NotFoundError()
    return parent_id


def _cycle(store: Any, actor: Actor, entity_id: uuid.UUID, parent_id: uuid.UUID | None) -> bool:
    current = parent_id
    seen: set[uuid.UUID] = set()
    while isinstance(current, uuid.UUID):
        if current == entity_id or current in seen:
            return True
        seen.add(current)
        row = bucket(store, "grc_entities").get(current)
        if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
            return False
        parent = row.get("parent_id")
        current = parent if isinstance(parent, uuid.UUID) else None
    return False


def _subtree(store: Any, actor: Actor, root: uuid.UUID) -> set[uuid.UUID]:
    children: dict[uuid.UUID | None, list[uuid.UUID]] = {}
    for row in bucket(store, "grc_entities").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        parent_raw = row.get("parent_id")
        parent = parent_raw if isinstance(parent_raw, uuid.UUID) else None
        child = row.get("id")
        if isinstance(child, uuid.UUID):
            children.setdefault(parent, []).append(child)
    found = {root}
    stack = [root]
    while stack:
        node = stack.pop()
        for child in children.get(node, []):
            if child not in found:
                found.add(child)
                stack.append(child)
    return found

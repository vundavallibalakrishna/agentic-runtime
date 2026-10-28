"""Control crosswalks. A suggestion stays suggested until a different person confirms it."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.demo_ids import demo_id
from ar_domain.records.memory import bucket
from ar_pack_grc.access import forbid, one, owned, present, record, same_tenant, snake_body

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

SUGGESTER = "grc-suggester"
CONFIRMER = "grc-confirmer"


def list_mappings(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(query)
    status = str(body.get("status") or "")
    source = str(body.get("from_control_id") or "")
    target = str(body.get("to_control_id") or "")
    items = []
    for row in owned(store, "grc_mappings", actor):
        if status and row.get("status") != status:
            continue
        if source and str(row.get("from_control_id")) != source:
            continue
        if target and str(row.get("to_control_id")) != target:
            continue
        items.append(present(row))
    return {"items": items, "next_cursor": None, "has_more": False}


def create_mapping(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(payload)
    source = _control(store, actor, body.get("from_control_id"))
    target = _control(store, actor, body.get("to_control_id"))
    if source["id"] == target["id"]:
        raise ValidationFailedError("a control cannot map to itself")
    confidence = _confidence(body.get("confidence"))
    confirmed = body.get("confirmed") is True
    if confirmed and confidence < 1:
        forbid("confirmer must be a different person")
    if confirmed and actor.kind != "user":
        forbid("suggestions are not confirmed by the agent")
    existing = _pair(store, actor, source["id"], target["id"])
    if existing is not None:
        return present(existing)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "from_control_id": source["id"],
        "to_control_id": target["id"],
        "confidence": confidence,
        "rationale": str(body.get("rationale") or ""),
        "status": "confirmed" if confirmed else "suggested",
        "suggested_by": actor.user_id,
        "confirmed_by": actor.user_id if confirmed else None,
        "confirmed_at": utcnow() if confirmed else None,
    }
    bucket(store, "grc_mappings")[item_id] = row
    if confirmed:
        record(store, actor, "grc.mapping.confirmed", item_id, {"confidence": confidence})
    return present(row)


def confirm_mapping(store: Any, actor: Actor, mapping_id: uuid.UUID) -> dict[str, Any]:
    row = one(store, "grc_mappings", actor, mapping_id)
    if actor.kind != "user":
        forbid("suggestions are not confirmed by the agent")
    if str(row.get("suggested_by") or "") == str(actor.user_id):
        forbid("confirmer must be a different person")
    if row.get("status") == "rejected":
        raise ConflictError("mapping was rejected")
    row["status"] = "confirmed"
    row["confirmed_by"] = actor.user_id
    row["confirmed_at"] = utcnow()
    record(store, actor, "grc.mapping.confirmed", mapping_id, {})
    return present(row)


def reject_mapping(store: Any, actor: Actor, mapping_id: uuid.UUID) -> dict[str, Any]:
    row = one(store, "grc_mappings", actor, mapping_id)
    row["status"] = "rejected"
    row["confirmed_by"] = None
    row["confirmed_at"] = None
    record(store, actor, "grc.mapping.rejected", mapping_id, {})
    return present(row)


def suggest(store: Any, actor: Actor, payload: dict[str, Any], *, agent: bool) -> dict[str, Any]:
    """Insert suggested rows only. Confirmation is a separate person."""
    body = snake_body(payload)
    source = _optional(store, actor, body.get("from_framework_id"))
    target = _optional(store, actor, body.get("to_framework_id"))
    if source is None or target is None:
        raise ValidationFailedError("from_framework_id and to_framework_id are required")
    suggester = demo_id("grc-agent") if agent else actor.user_id
    created = 0
    for spec in _pairs_between(store, actor, source, target):
        if _pair(store, actor, spec["from_control_id"], spec["to_control_id"]) is not None:
            continue
        item_id = new_id()
        bucket(store, "grc_mappings")[item_id] = {
            "id": item_id,
            "tenant_id": actor.tenant_id,
            "from_control_id": spec["from_control_id"],
            "to_control_id": spec["to_control_id"],
            "confidence": spec["confidence"],
            "rationale": spec["rationale"],
            "status": "suggested",
            "suggested_by": suggester,
            "confirmed_by": None,
            "confirmed_at": None,
        }
        created += 1
    run_id = new_id()
    bucket(store, "grc_jobs")[run_id] = {
        "id": run_id,
        "tenant_id": actor.tenant_id,
        "kind": "mapping.suggest",
        "agent": agent,
        "created": created,
    }
    return {"run_id": str(run_id), "created": created}


def seed_common(store: Any, actor: Actor, catalogue: dict[str, Any]) -> None:
    """Seed CC-* controls and the shipped crosswalk."""
    controls = catalogue.get("controls")
    if not isinstance(controls, list):
        return
    by_key = _controls_by_framework(store, actor)
    for spec in controls:
        if not isinstance(spec, dict):
            continue
        common = _ensure_common(store, actor, spec)
        mappings = spec.get("mappings")
        if not isinstance(mappings, list):
            continue
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            other = by_key.get((str(mapping.get("framework")), str(mapping.get("control")).lower()))
            if other is None:
                continue
            _ensure_seed_mapping(store, actor, common["id"], other, mapping)


def _ensure_common(store: Any, actor: Actor, spec: dict[str, Any]) -> dict[str, Any]:
    key = str(spec.get("key") or "")
    for row in owned(store, "grc_controls", actor):
        if row.get("framework_id") is None and row.get("key") == key:
            return row
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "framework_id": None,
        "entity_id": None,
        "key": key,
        "title": str(spec.get("title") or key),
        "statement": str(spec.get("statement") or ""),
        "owner_user_id": None,
    }
    bucket(store, "grc_controls")[item_id] = row
    return row


def _ensure_seed_mapping(
    store: Any,
    actor: Actor,
    common_id: uuid.UUID,
    other_id: uuid.UUID,
    spec: dict[str, Any],
) -> None:
    if _pair(store, actor, common_id, other_id) is not None:
        return
    status = str(spec.get("status") or "suggested")
    confirmed = status == "confirmed"
    item_id = new_id()
    bucket(store, "grc_mappings")[item_id] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "from_control_id": common_id,
        "to_control_id": other_id,
        "confidence": _confidence(spec.get("confidence")),
        "rationale": "shipped crosswalk",
        "status": "confirmed" if confirmed else "suggested",
        "suggested_by": demo_id(SUGGESTER),
        "confirmed_by": demo_id(CONFIRMER) if confirmed else None,
        "confirmed_at": utcnow() if confirmed else None,
    }


def _pairs_between(
    store: Any, actor: Actor, source: uuid.UUID, target: uuid.UUID
) -> list[dict[str, Any]]:
    """One suggested pair between the two frameworks. It is never confirmed here."""
    left = [row for row in owned(store, "grc_controls", actor) if row.get("framework_id") == source]
    right = [
        row for row in owned(store, "grc_controls", actor) if row.get("framework_id") == target
    ]
    if not left or not right:
        return []
    return [
        {
            "from_control_id": left[0]["id"],
            "to_control_id": right[0]["id"],
            "confidence": 0.5,
            "rationale": "crosswalk suggestion",
        }
    ]


def _controls_by_framework(store: Any, actor: Actor) -> dict[tuple[str, str], uuid.UUID]:
    frameworks = {row["id"]: str(row["key"]) for row in owned(store, "grc_frameworks", actor)}
    found: dict[tuple[str, str], uuid.UUID] = {}
    for row in owned(store, "grc_controls", actor):
        framework = frameworks.get(row.get("framework_id"))
        if framework:
            found[(framework, str(row["key"]))] = row["id"]
    return found


def _pair(store: Any, actor: Actor, source: uuid.UUID, target: uuid.UUID) -> dict[str, Any] | None:
    for row in bucket(store, "grc_mappings").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if row.get("from_control_id") == source and row.get("to_control_id") == target:
            return row
    return None


def _control(store: Any, actor: Actor, value: object) -> dict[str, Any]:
    try:
        item_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError("control id is not a uuid") from exc
    return one(store, "grc_controls", actor, item_id)


def _optional(store: Any, actor: Actor, value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        item_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError("framework id is not a uuid") from exc
    one(store, "grc_frameworks", actor, item_id)
    return item_id


def _confidence(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValidationFailedError("confidence must be between 0 and 1") from exc
    if number < 0 or number > 1:
        raise ValidationFailedError("confidence must be between 0 and 1")
    return number

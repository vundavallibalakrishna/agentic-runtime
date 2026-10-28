"""Business segregation rules. They never write core ``sod_constraints``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import required_text

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor


def list_rules(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_sod_rules").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def create_rule(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.campaigns:manage")
    body = snake_body(payload)
    left, right = _pair(body.get("entitlement_a"), body.get("entitlement_b"))
    _unused(store, actor, left, right, None)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "name": required_text(body.get("name"), "name"),
        "entitlement_a": left,
        "entitlement_b": right,
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_sod_rules")[item_id] = row
    return present(row)


def update_rule(
    store: Any, actor: Actor, rule_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.campaigns:manage")
    row = one(store, "grc_sod_rules", actor, rule_id)
    body = snake_body(payload)
    if body.get("name"):
        row["name"] = required_text(body.get("name"), "name")
    if body.get("entitlement_a") or body.get("entitlement_b"):
        left, right = _pair(
            body.get("entitlement_a") or row.get("entitlement_a"),
            body.get("entitlement_b") or row.get("entitlement_b"),
        )
        _unused(store, actor, left, right, rule_id)
        row["entitlement_a"] = left
        row["entitlement_b"] = right
    return present(row)


def delete_rule(store: Any, actor: Actor, rule_id: uuid.UUID) -> None:
    require(actor, "grc.campaigns:manage")
    one(store, "grc_sod_rules", actor, rule_id)
    bucket_rows(store, "grc_sod_rules").pop(rule_id, None)


def matching(store: Any, actor: Actor, subject: str) -> list[str]:
    """Rule names whose pair is both held by ``subject``."""
    if not subject:
        return []
    held = {
        str(row.get("entitlement") or "")
        for row in bucket_rows(store, "grc_entitlements").values()
        if same_tenant(row, actor.tenant_id) and str(row.get("subject") or "") == subject
    }
    names = [
        str(row.get("name") or "")
        for row in bucket_rows(store, "grc_sod_rules").values()
        if same_tenant(row, actor.tenant_id)
        and str(row.get("entitlement_a") or "") in held
        and str(row.get("entitlement_b") or "") in held
    ]
    names.sort()
    return names


def _pair(left: object, right: object) -> tuple[str, str]:
    first = required_text(left, "entitlement_a")
    second = required_text(right, "entitlement_b")
    if first == second:
        raise ValidationFailedError("entitlements must differ")
    return first, second


def _unused(store: Any, actor: Actor, left: str, right: str, current: uuid.UUID | None) -> None:
    for row in bucket_rows(store, "grc_sod_rules").values():
        if not same_tenant(row, actor.tenant_id) or row.get("id") == current:
            continue
        pair = {str(row.get("entitlement_a")), str(row.get("entitlement_b"))}
        if pair == {left, right}:
            raise ValidationFailedError("that pair already exists")

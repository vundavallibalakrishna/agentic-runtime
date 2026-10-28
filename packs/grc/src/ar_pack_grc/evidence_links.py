"""Links from a control to a core evidence item. Deleting a link leaves the evidence."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ar_common.errors import ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, present, record, same_tenant, snake_body

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def list_links(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    body = snake_body(query)
    control_id = str(body.get("control_id") or "")
    stale_only = str(body.get("stale") or "").lower() == "true"
    items = []
    for row in bucket(store, "grc_evidence_links").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if control_id and str(row.get("control_id")) != control_id:
            continue
        item = _view(store, row)
        if stale_only and not item["stale"]:
            continue
        items.append(item)
    return {"items": items, "next_cursor": None, "has_more": False}


def create_link(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.evidence:link")
    require(actor, "evidence:read")
    body = snake_body(payload)
    control = one(store, "grc_controls", actor, _uuid(body.get("control_id")))
    evidence_id = _uuid(body.get("evidence_item_id"))
    evidence = bucket(store, "evidence").get(evidence_id)
    if not isinstance(evidence, dict) or not same_tenant(evidence, actor.tenant_id):
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError()
    freshness = _days(body.get("freshness_days"))
    for row in bucket(store, "grc_evidence_links").values():
        if row.get("control_id") == control["id"] and row.get("evidence_item_id") == evidence_id:
            return _view(store, row)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "control_id": control["id"],
        "evidence_item_id": evidence_id,
        "freshness_days": freshness,
        "created_at": utcnow(),
    }
    bucket(store, "grc_evidence_links")[item_id] = row
    record(
        store,
        actor,
        "grc.evidence.linked",
        item_id,
        {"control_id": str(control["id"]), "evidence_item_id": str(evidence_id)},
    )
    return _view(store, row)


def delete_link(store: Any, actor: Actor, link_id: uuid.UUID) -> None:
    row = one(store, "grc_evidence_links", actor, link_id)
    evidence_id = row.get("evidence_item_id")
    bucket(store, "grc_evidence_links").pop(link_id, None)
    record(store, actor, "grc.evidence.linked", link_id, {"removed": True})
    if evidence_id is not None and evidence_id not in bucket(store, "evidence"):
        from ar_common.errors import ConflictError  # noqa: PLC0415

        raise ConflictError("evidence item disappeared")


def _view(store: Any, row: dict[str, Any]) -> dict[str, Any]:
    evidence = bucket(store, "evidence").get(row.get("evidence_item_id"))
    collected = evidence.get("collected_at") if isinstance(evidence, dict) else None
    item = present(row)
    item["collected_at"] = collected.isoformat() if isinstance(collected, datetime) else collected
    item["stale"] = _stale(collected, int(row["freshness_days"]))
    return item


def _stale(collected: object, freshness_days: int) -> bool:
    if not isinstance(collected, datetime):
        return False
    return utcnow() > collected + timedelta(days=freshness_days)


def _uuid(value: object) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError("id is not a uuid") from exc


def _days(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValidationFailedError("freshness_days must be at least 1")
    try:
        days = int(value)
    except ValueError as exc:
        raise ValidationFailedError("freshness_days must be at least 1") from exc
    if days < 1:
        raise ValidationFailedError("freshness_days must be at least 1")
    return days

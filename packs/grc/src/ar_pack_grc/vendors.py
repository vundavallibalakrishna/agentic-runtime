"""Vendors, assessments and the SOC 2 report skill."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from ar_common.errors import ForbiddenError, NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.campaigns import create_campaign
from ar_pack_grc.values import choice, required_text, string_list, when

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

VENDOR_PORTAL = "vendor"
_TIERS = frozenset({"critical", "high", "medium", "low"})
_KINDS = frozenset({"intake", "questionnaire", "document_review"})
_EXCEPTION = re.compile(r"(?im)^exception:\s*(.+)$")
_CUEC = re.compile(r"(?im)^cuec:\s*(.+)$")
_BRIDGE = re.compile(r"(?im)^bridge gap:\s*(.+)$")


def register_portal(store: Any) -> None:
    """The vendor guest portal. Core already allows `/api/v1/ext/`."""
    bucket(store, "pack_portals")[VENDOR_PORTAL] = {"pack_id": "grc", "portal": VENDOR_PORTAL}


def list_vendors(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.vendors:read")
    body = snake_body(query)
    tier = str(body.get("tier") or "")
    text = str(body.get("q") or "").lower()
    items = []
    for row in bucket_rows(store, "grc_vendors").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if tier and str(row.get("tier") or "") != tier:
            continue
        if text and text not in str(row.get("name") or "").lower():
            continue
        items.append(present(row))
    return page(items)


def create_vendor(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.vendors:manage")
    body = snake_body(payload)
    name = required_text(body.get("name"), "name")
    item_id = new_id()
    now = utcnow()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "name": name,
        "tier": body.get("tier"),
        "owner_user_id": body.get("owner_user_id") or actor.user_id,
        "created_at": now,
        "updated_at": now,
    }
    bucket_rows(store, "grc_vendors")[item_id] = row
    record(store, actor, "grc.vendor.created", item_id, {"name": name})
    return present(row)


def get_vendor(store: Any, actor: Actor, vendor_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.vendors:read")
    row = one(store, "grc_vendors", actor, vendor_id)
    body = present(row)
    body["assessments"] = _assessments(store, actor, vendor_id, granted=None)
    return body


def patch_vendor(
    store: Any, actor: Actor, vendor_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.vendors:manage")
    row = one(store, "grc_vendors", actor, vendor_id)
    body = snake_body(payload)
    if "name" in body:
        row["name"] = required_text(body.get("name"), "name")
    if "owner_user_id" in body:
        row["owner_user_id"] = body.get("owner_user_id")
    if "tier" in body and body.get("tier"):
        row["tier"] = choice(body.get("tier"), _TIERS, "tier")
    row["updated_at"] = utcnow()
    return present(row)


def list_assessments(store: Any, actor: Actor, vendor_id: uuid.UUID) -> dict[str, Any]:
    one(store, "grc_vendors", actor, vendor_id)
    granted = _granted(store, actor) if actor.kind == "guest" else None
    if granted is None:
        require(actor, "grc.vendors:read")
    return page(_assessments(store, actor, vendor_id, granted=granted))


def create_assessment(
    store: Any, actor: Actor, vendor_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.vendors:manage")
    vendor = one(store, "grc_vendors", actor, vendor_id)
    body = snake_body(payload)
    kind = choice(body.get("kind"), _KINDS, "kind")
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "vendor_id": vendor_id,
        "kind": kind,
        "status": "open",
        "tier": None,
        "rationale": "",
        "evidence_item_ids": [],
        "due_at": when(body.get("due_at")),
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_vendor_assessments")[item_id] = row
    if kind == "questionnaire":
        create_campaign(
            store,
            actor,
            {"kind": "vendor", "title": f"{vendor.get('name')} questionnaire"},
            trusted=True,
        )
    return present(row)


def score_assessment(
    store: Any, actor: Actor, assessment_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.vendors:manage")
    row = one(store, "grc_vendor_assessments", actor, assessment_id)
    body = snake_body(payload)
    tier = choice(body.get("tier"), _TIERS, "tier")
    row["tier"] = tier
    row["rationale"] = str(body.get("rationale") or "")
    row["evidence_item_ids"] = string_list(body.get("evidence_item_ids"))
    row["status"] = "scored"
    vendor = one(store, "grc_vendors", actor, row["vendor_id"])
    vendor["tier"] = tier
    vendor["updated_at"] = utcnow()
    record(
        store,
        actor,
        "grc.assessment.completed",
        assessment_id,
        {"tier": tier, "vendor_id": str(row["vendor_id"])},
    )
    return present(row)


def review_soc2(text: str) -> dict[str, Any]:
    """Extract exceptions, CUECs and bridge-letter gaps. The skill cites the evidence item."""
    return {
        "exceptions": _lines(_EXCEPTION, text),
        "cuecs": _lines(_CUEC, text),
        "bridge_letter_gaps": _lines(_BRIDGE, text),
    }


def _lines(pattern: re.Pattern[str], text: str) -> list[str]:
    return [match.group(1).strip() for match in pattern.finditer(text)]


def _assessments(
    store: Any, actor: Actor, vendor_id: uuid.UUID, *, granted: set[str] | None
) -> list[dict[str, Any]]:
    found = []
    for row in bucket_rows(store, "grc_vendor_assessments").values():
        if not same_tenant(row, actor.tenant_id) or row.get("vendor_id") != vendor_id:
            continue
        if granted is not None and str(row.get("id")) not in granted:
            continue
        found.append(present(row))
    found.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return found


def _granted(store: Any, actor: Actor) -> set[str]:
    found: set[str] = set()
    for grant in bucket(store, "guest_grants").values():
        if not isinstance(grant, dict):
            continue
        if grant.get("guest_id") != actor.user_id and str(grant.get("guest_id")) != str(
            actor.user_id
        ):
            continue
        if grant.get("portal") != VENDOR_PORTAL:
            continue
        scope = grant.get("scope")
        raw = scope.get("pack_record_ids") if isinstance(scope, dict) else []
        if isinstance(raw, list):
            found.update(str(item) for item in raw)
    return found


def get_assessment_for_guest(store: Any, actor: Actor, assessment_id: uuid.UUID) -> dict[str, Any]:
    """A guest sees one granted assessment. Anything else is 404."""
    if actor.kind != "guest":
        raise ForbiddenError()
    if str(assessment_id) not in _granted(store, actor):
        raise NotFoundError()
    return present(one(store, "grc_vendor_assessments", actor, assessment_id))

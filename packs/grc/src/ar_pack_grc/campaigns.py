"""Campaigns. Start, close and decisions record a core sign-off for attestations."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, ForbiddenError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.identity.service import assert_step_up
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import open_review
from ar_pack_grc.sod_rules import matching
from ar_pack_grc.values import as_uuid, required_text

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_KINDS = frozenset({"questionnaire", "vendor", "acknowledgement", "attestation", "access_review"})
_SIGN = frozenset({"acknowledgement", "attestation", "access_review"})


def list_campaigns(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    body = snake_body(query)
    kind = str(body.get("kind") or "")
    items = [
        _view(store, row)
        for row in bucket_rows(store, "grc_campaigns").values()
        if same_tenant(row, actor.tenant_id) and (not kind or str(row.get("kind")) == kind)
    ]
    return page(items)


def create_campaign(
    store: Any, actor: Actor, payload: dict[str, Any], *, trusted: bool = False
) -> dict[str, Any]:
    if not trusted:
        require(actor, "grc.campaigns:manage")
    body = snake_body(payload)
    kind = required_text(body.get("kind"), "kind")
    if kind not in _KINDS:
        from ar_common.errors import ValidationFailedError  # noqa: PLC0415

        raise ValidationFailedError("kind is invalid")
    title = required_text(body.get("title"), "title")
    item_id = new_id()
    row: dict[str, Any] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "kind": kind,
        "title": title,
        "status": "draft",
        "due_at": _when(body.get("due_at")),
        "audience": _audience(body.get("audience")),
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_campaigns")[item_id] = row
    return _view(store, row)


def get_campaign(store: Any, actor: Actor, campaign_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    return _view(store, one(store, "grc_campaigns", actor, campaign_id))


def start_campaign(store: Any, actor: Actor, campaign_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.campaigns:manage")
    row = one(store, "grc_campaigns", actor, campaign_id)
    if row.get("status") == "closed":
        raise ConflictError("closed")
    if row.get("status") == "draft":
        _materialise(store, actor, row)
        row["status"] = "running"
        record(store, actor, "grc.campaign.started", row["id"], {"kind": row.get("kind")})
    return _view(store, row)


def close_campaign(
    store: Any, actor: Actor, campaign_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.campaigns:manage")
    row = one(store, "grc_campaigns", actor, campaign_id)
    if row.get("status") == "closed":
        return _view(store, row)
    if row.get("status") != "running":
        raise ConflictError("not_running")
    body = snake_body(payload)
    if _open_items(store, row["id"]) and not body.get("force"):
        raise ConflictError("open_items")
    if _open_items(store, row["id"]):
        assert_step_up(actor.step_up_at, now=utcnow(), ttl_s=600, required=True)
    row["status"] = "closed"
    return _view(store, row)


def list_items(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    body = snake_body(query)
    campaign_id = str(body.get("campaign_id") or "")
    status = str(body.get("status") or "")
    assignee = str(body.get("assignee") or "")
    items = []
    for row in bucket_rows(store, "grc_campaign_items").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if campaign_id and str(row.get("campaign_id")) != campaign_id:
            continue
        if status and str(row.get("status")) != status:
            continue
        if assignee == "me" and str(row.get("assignee_user_id") or "") != str(actor.user_id):
            continue
        items.append(_item_view(store, actor, row))
    return page(items)


def decide_item(
    store: Any, actor: Actor, item_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    row = one(store, "grc_campaign_items", actor, item_id)
    _allow(actor, row)
    if row.get("status") == "decided":
        return _item_view(store, actor, row)
    body = snake_body(payload)
    statement = required_text(body.get("statement_text"), "statement_text")
    decision = required_text(body.get("decision"), "decision")
    campaign = one(store, "grc_campaigns", actor, row["campaign_id"])
    if campaign.get("kind") in _SIGN:
        _sign(store, actor, row, statement, decision)
    else:
        row["statement_hash"] = hashlib.sha256(statement.encode()).hexdigest()
    row["statement_text"] = statement
    row["decision"] = decision
    row["status"] = "decided"
    record(store, actor, "grc.campaign_item.decided", row["id"], {"decision": decision})
    if campaign.get("kind") == "acknowledgement":
        raw_audience = campaign.get("audience")
        audience: dict[str, Any] = raw_audience if isinstance(raw_audience, dict) else {}
        target = audience.get("policy_id") or row["id"]
        record(
            store,
            actor,
            "grc.policy.acknowledged",
            target,
            {"statement_hash": row["statement_hash"]},
        )
    return _item_view(store, actor, row)


def _sign(store: Any, actor: Actor, row: dict[str, Any], statement: str, decision: str) -> None:
    review = open_review(
        store,
        actor,
        slug="grc-campaigns",
        subject_id=row["id"],
        content=statement,
        statement=statement,
    )
    saved = store.review_items.get(review.get("id"))
    if isinstance(saved, dict):
        saved["status"] = "signed"
        saved["updated_at"] = utcnow()
    signoff_id = new_id()
    store.signoffs[signoff_id] = {
        "id": signoff_id,
        "tenant_id": actor.tenant_id,
        "review_item_id": review.get("id"),
        "level": 1,
        "decision": decision,
        "signer_principal_type": actor.kind,
        "signer_principal_id": actor.user_id,
        "content_hash": review.get("content_hash"),
        "statement_hash": review.get("statement_hash"),
        "comment": "",
        "created_at": utcnow(),
    }
    row["review_item_id"] = review.get("id")
    row["statement_hash"] = review.get("statement_hash")


def _materialise(store: Any, actor: Actor, campaign: dict[str, Any]) -> None:
    raw_audience = campaign.get("audience")
    audience: dict[str, Any] = raw_audience if isinstance(raw_audience, dict) else {}
    for spec in _assignees(audience):
        user_id = as_uuid(spec.get("user_id"), required=False)
        guest_id = as_uuid(spec.get("guest_id"), required=False)
        if _assigned(store, campaign["id"], user_id, guest_id):
            continue
        item_id = new_id()
        subject = str(spec.get("subject") or user_id or guest_id or "")
        bucket_rows(store, "grc_campaign_items")[item_id] = {
            "id": item_id,
            "tenant_id": actor.tenant_id,
            "campaign_id": campaign["id"],
            "assignee_user_id": user_id,
            "assignee_guest_id": guest_id,
            "subject": subject,
            "status": "open",
            "decision": None,
            "statement_text": "",
            "statement_hash": None,
            "review_item_id": None,
            "sod_conflicts": [],
        }
        _notify(store, actor, user_id, str(campaign.get("title") or ""))


def _audience(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    body = snake_body(raw)
    assignees = body.get("assignees")
    if isinstance(assignees, list):
        body["assignees"] = [
            snake_body(item) if isinstance(item, dict) else item for item in assignees
        ]
    return body


def _assignees(audience: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    raw = audience.get("assignees")
    if isinstance(raw, list):
        found.extend(item for item in raw if isinstance(item, dict))
    values = audience.get("user_ids")
    if isinstance(values, list):
        found.extend({"user_id": item, "subject": str(item)} for item in values)
    guests = audience.get("guest_ids")
    if isinstance(guests, list):
        found.extend({"guest_id": item, "subject": str(item)} for item in guests)
    return found


def _assigned(store: Any, campaign_id: object, user_id: object, guest_id: object) -> bool:
    for row in bucket_rows(store, "grc_campaign_items").values():
        if row.get("campaign_id") != campaign_id:
            continue
        if row.get("assignee_user_id") == user_id and row.get("assignee_guest_id") == guest_id:
            return True
    return False


def _notify(store: Any, actor: Actor, user_id: object, title: str) -> None:
    if user_id is None:
        return
    notes = getattr(store, "notifications", None)
    if isinstance(notes, list):
        notes.append(
            {
                "tenant_id": actor.tenant_id,
                "user_id": user_id,
                "kind": "grc.campaign.started",
                "title": title,
                "created_at": utcnow(),
            }
        )


def _open_items(store: Any, campaign_id: object) -> list[dict[str, Any]]:
    return [
        row
        for row in bucket_rows(store, "grc_campaign_items").values()
        if row.get("campaign_id") == campaign_id and row.get("status") == "open"
    ]


def _allow(actor: Actor, row: dict[str, Any]) -> None:
    if actor.has("grc.campaigns:manage"):
        return
    if str(row.get("assignee_user_id") or "") == str(actor.user_id):
        return
    if actor.kind == "guest" and str(row.get("assignee_guest_id") or "") == str(actor.user_id):
        return
    raise ForbiddenError()


def _view(store: Any, row: dict[str, Any]) -> dict[str, Any]:
    body = present(row)
    campaign_id = row.get("id")
    items = [
        item
        for item in bucket_rows(store, "grc_campaign_items").values()
        if item.get("campaign_id") == campaign_id
    ]
    body["item_count"] = len(items)
    body["open_count"] = sum(1 for item in items if item.get("status") == "open")
    return body


def _item_view(store: Any, actor: Actor, row: dict[str, Any]) -> dict[str, Any]:
    campaign = bucket_rows(store, "grc_campaigns").get(row.get("campaign_id"))
    if isinstance(campaign, dict) and campaign.get("kind") == "access_review":
        row["sod_conflicts"] = matching(store, actor, str(row.get("subject") or ""))
    return present(row)


def _when(value: object) -> object:
    from ar_pack_grc.values import when  # noqa: PLC0415

    return when(value)

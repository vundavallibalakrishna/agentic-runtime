"""Assets, risks, assessments and treatments. Acceptance waits for sign-off."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import audited, open_review, signed_for
from ar_pack_grc.values import choice, required_text, scale, when

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_TREATMENT = frozenset({"mitigate", "transfer", "avoid"})


def list_assets(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.risks:read")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_assets").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def create_asset(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.risks:manage")
    body = snake_body(payload)
    kind = required_text(body.get("kind"), "kind")
    owner = body.get("owner_user_id")
    tier = str(body.get("tier") or "").strip()
    if kind == "model" and not str(owner or "").strip():
        from ar_common.errors import ValidationFailedError  # noqa: PLC0415

        raise ValidationFailedError("owner is required")
    if kind == "model" and not tier:
        from ar_common.errors import ValidationFailedError  # noqa: PLC0415

        raise ValidationFailedError("tier is required")
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "name": required_text(body.get("name"), "name"),
        "kind": kind,
        "owner_user_id": owner or None,
        "tier": tier or None,
        "agent_card_id": body.get("agent_card_id") or None,
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_assets")[item_id] = row
    return present(row)


def list_risks(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.risks:read")
    _sync_acceptance(store, actor)
    body = snake_body(query)
    status = str(body.get("status") or "")
    asset_id = str(body.get("asset_id") or "")
    items = []
    for row in bucket_rows(store, "grc_risks").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if status and str(row.get("status")) != status:
            continue
        if asset_id and str(row.get("asset_id") or "") != asset_id:
            continue
        items.append(_view(store, actor, row))
    return page(items)


def create_risk(
    store: Any, actor: Actor, payload: dict[str, Any], *, source: str = "human"
) -> dict[str, Any]:
    require(actor, "grc.risks:manage")
    body = snake_body(payload)
    if body.get("source") == "agent":
        source = "agent"
    title = required_text(body.get("title"), "title")
    statement = required_text(body.get("statement"), "statement")
    asset_id = body.get("asset_id")
    if asset_id:
        one(store, "grc_assets", actor, uuid.UUID(str(asset_id)))
    likelihood = scale(body.get("likelihood"))
    impact = scale(body.get("impact"))
    item_id = new_id()
    now = utcnow()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "asset_id": asset_id,
        "title": title,
        "statement": statement,
        "status": "open",
        "source": source,
        "acceptance": None,
        "created_at": now,
        "updated_at": now,
    }
    bucket_rows(store, "grc_risks")[item_id] = row
    _assess(store, actor, row, likelihood, impact)
    if source == "agent":
        record(store, actor, "grc.risk.proposed", item_id, {"title": title})
    return _view(store, actor, row)


def propose(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    """W1 tool. The analyst proposes. A person accepts."""
    body = snake_body(payload)
    body["source"] = "agent"
    return create_risk(store, actor, body, source="agent")


def get_risk(store: Any, actor: Actor, risk_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.risks:read")
    _sync_acceptance(store, actor)
    return _view(store, actor, one(store, "grc_risks", actor, risk_id))


def patch_risk(
    store: Any, actor: Actor, risk_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.risks:manage")
    row = one(store, "grc_risks", actor, risk_id)
    body = snake_body(payload)
    if "statement" in body:
        row["statement"] = required_text(body.get("statement"), "statement")
    if "title" in body:
        row["title"] = required_text(body.get("title"), "title")
    if "likelihood" in body or "impact" in body:
        latest = _latest(store, row["id"])
        likelihood = scale(body.get("likelihood", latest.get("likelihood")))
        impact = scale(body.get("impact", latest.get("impact")))
        if likelihood != latest.get("likelihood") or impact != latest.get("impact"):
            _assess(store, actor, row, likelihood, impact)
    row["updated_at"] = utcnow()
    return _view(store, actor, row)


def accept_risk(
    store: Any, actor: Actor, risk_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.risks:manage")
    row = one(store, "grc_risks", actor, risk_id)
    body = snake_body(payload)
    statement = required_text(body.get("statement_text"), "statement_text")
    expires = when(body.get("expires_at"), required=True)
    item = open_review(
        store,
        actor,
        slug="grc-risks",
        subject_id=risk_id,
        content=statement,
        statement=statement,
    )
    row["status"] = "proposed"
    row["acceptance"] = {
        "statement_text": statement,
        "expires_at": expires,
        "review_item_id": item.get("id"),
        "content_hash": item.get("content_hash"),
    }
    row["updated_at"] = utcnow()
    return _view(store, actor, row)


def list_treatments(store: Any, actor: Actor, risk_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.risks:read")
    one(store, "grc_risks", actor, risk_id)
    items = [
        present(row)
        for row in bucket_rows(store, "grc_treatments").values()
        if same_tenant(row, actor.tenant_id) and row.get("risk_id") == risk_id
    ]
    return page(items)


def add_treatment(
    store: Any, actor: Actor, risk_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.risks:manage")
    one(store, "grc_risks", actor, risk_id)
    body = snake_body(payload)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "risk_id": risk_id,
        "kind": choice(body.get("kind"), _TREATMENT, "kind"),
        "plan": required_text(body.get("plan"), "plan"),
        "owner_user_id": body.get("owner_user_id") or actor.user_id,
        "due_at": when(body.get("due_at")),
        "status": "open",
    }
    bucket_rows(store, "grc_treatments")[item_id] = row
    return present(row)


def _assess(
    store: Any, actor: Actor, risk: dict[str, Any], likelihood: int, impact: int
) -> dict[str, Any]:
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "risk_id": risk["id"],
        "likelihood": likelihood,
        "impact": impact,
        "score": likelihood * impact,
        "created_by": actor.user_id,
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_risk_assessments")[item_id] = row
    return row


def _latest(store: Any, risk_id: object) -> dict[str, Any]:
    rows = [
        row
        for row in bucket_rows(store, "grc_risk_assessments").values()
        if row.get("risk_id") == risk_id
    ]
    rows.sort(key=lambda row: str(row.get("created_at") or ""))
    return rows[-1] if rows else {}


def _view(store: Any, actor: Actor, row: dict[str, Any]) -> dict[str, Any]:
    body = present(row)
    body["assessments"] = [
        present(item)
        for item in bucket_rows(store, "grc_risk_assessments").values()
        if same_tenant(item, actor.tenant_id) and item.get("risk_id") == row["id"]
    ]
    body["treatments"] = [
        present(item)
        for item in bucket_rows(store, "grc_treatments").values()
        if same_tenant(item, actor.tenant_id) and item.get("risk_id") == row["id"]
    ]
    return body


def _sync_acceptance(store: Any, actor: Actor) -> None:
    for row in bucket_rows(store, "grc_risks").values():
        if not same_tenant(row, actor.tenant_id) or row.get("status") != "proposed":
            continue
        acceptance = row.get("acceptance")
        if not isinstance(acceptance, dict):
            continue
        digest = str(acceptance.get("content_hash") or "")
        if signed_for(store, row["id"], digest) is None:
            continue
        row["status"] = "accepted"
        row["updated_at"] = utcnow()
        if not audited(store, "grc.risk.accepted", row["id"]):
            record(store, actor, "grc.risk.accepted", row["id"], {"content_hash": digest})

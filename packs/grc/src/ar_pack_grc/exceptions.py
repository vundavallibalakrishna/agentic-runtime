"""Exceptions and waivers. A waiver needs a compensating control. Expiry is a daily sweep."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ar_common.errors import ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import audited, open_review, signed_for
from ar_pack_grc.values import choice, required_text, when

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_KINDS = frozenset({"exception", "waiver"})


def list_exceptions(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.controls:read")
    sync_signed(store, actor)
    body = snake_body(query)
    control_id = str(body.get("control_id") or "")
    status = str(body.get("status") or "")
    items = []
    for row in bucket_rows(store, "grc_exceptions").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if control_id and str(row.get("control_id")) != control_id:
            continue
        if status and str(row.get("status")) != status:
            continue
        items.append(present(row))
    return page(items)


def create_exception(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.exceptions:manage")
    body = snake_body(payload)
    kind = choice(body.get("kind"), _KINDS, "kind")
    control_id = uuid.UUID(str(body.get("control_id")))
    one(store, "grc_controls", actor, control_id)
    compensating = body.get("compensating_control_id")
    if kind == "waiver" and not compensating:
        raise ValidationFailedError("compensating_control_id is required")
    compensating_id = None
    if compensating:
        compensating_id = uuid.UUID(str(compensating))
        one(store, "grc_controls", actor, compensating_id)
    rationale = required_text(body.get("rationale"), "rationale")
    expires = when(body.get("expires_at"), required=True)
    if expires is None:
        raise ValidationFailedError("time is required")
    item_id = new_id()
    content = f"{kind}:{rationale}:{expires.isoformat()}"
    review = open_review(
        store,
        actor,
        slug="grc-exceptions",
        subject_id=item_id,
        content=content,
        statement=f"I sign this {kind}.",
    )
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "control_id": control_id,
        "kind": kind,
        "rationale": rationale,
        "compensating_control_id": compensating_id,
        "expires_at": expires,
        "status": "proposed",
        "review_item_id": review.get("id"),
        "content_hash": review.get("content_hash"),
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_exceptions")[item_id] = row
    return present(row)


def sync_signed(store: Any, actor: Actor) -> int:
    changed = 0
    for row in bucket_rows(store, "grc_exceptions").values():
        if not same_tenant(row, actor.tenant_id) or row.get("status") != "proposed":
            continue
        if signed_for(store, row["id"], str(row.get("content_hash") or "")) is None:
            continue
        row["status"] = "signed"
        if not audited(store, "grc.exception.signed", row["id"]):
            record(store, actor, "grc.exception.signed", row["id"], {"kind": row.get("kind")})
        changed += 1
    return changed


def expire_due(store: Any, actor: Actor, *, now: datetime | None = None) -> int:
    """Daily routine. A passed `expires_at` becomes `expired`."""
    moment = now or utcnow()
    changed = 0
    for row in bucket_rows(store, "grc_exceptions").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if row.get("status") not in {"proposed", "signed"}:
            continue
        expires = row.get("expires_at")
        if not isinstance(expires, datetime) or expires > moment:
            continue
        row["status"] = "expired"
        changed += 1
    return changed


def covering_exception(store: Any, actor: Actor, control_id: object) -> dict[str, Any] | None:
    """A signed exception that has not expired. Expired rows are ignored."""
    now = utcnow()
    for row in bucket_rows(store, "grc_exceptions").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if row.get("control_id") != control_id and str(row.get("control_id")) != str(control_id):
            continue
        if row.get("status") != "signed":
            continue
        expires = row.get("expires_at")
        if isinstance(expires, datetime) and expires <= now:
            continue
        return row
    return None

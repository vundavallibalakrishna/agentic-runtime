"""Campaigns opened by M18. Start, close and decisions land in M19."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import required_text, when

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_KINDS = frozenset({"questionnaire", "vendor", "acknowledgement", "attestation", "access_review"})


def list_campaigns(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    body = snake_body(query)
    kind = str(body.get("kind") or "")
    items = []
    for row in bucket_rows(store, "grc_campaigns").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if kind and str(row.get("kind")) != kind:
            continue
        items.append(_view(store, row))
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
        "due_at": when(body.get("due_at")),
        "audience": body.get("audience") if isinstance(body.get("audience"), dict) else {},
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_campaigns")[item_id] = row
    return _view(store, row)


def get_campaign(store: Any, actor: Actor, campaign_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    return _view(store, one(store, "grc_campaigns", actor, campaign_id))


def _view(store: Any, row: dict[str, Any]) -> dict[str, Any]:
    body = present(row)
    campaign_id = row.get("id")
    count = 0
    for item in bucket_rows(store, "grc_campaign_items").values():
        if item.get("campaign_id") == campaign_id:
            count += 1
    body["item_count"] = count
    return body

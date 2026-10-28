"""Restricted ethics cases. A missing permission is a 404, not a confirmation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ForbiddenError, NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import required_text

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def list_cases(store: Any, actor: Actor) -> dict[str, Any]:
    if not actor.has("grc.ethics:manage"):
        return page([])
    items = [
        present(row)
        for row in bucket_rows(store, "grc_ethics_cases").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def get_case(store: Any, actor: Actor, case_id: uuid.UUID) -> dict[str, Any]:
    if not actor.has("grc.ethics:manage"):
        raise NotFoundError()
    row = one(store, "grc_ethics_cases", actor, case_id)
    if row.get("restricted") is True and not actor.has("grc.ethics:manage"):
        raise NotFoundError()
    return present(row)


def open_case(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    if not actor.has("grc.ethics:manage"):
        raise ForbiddenError()
    body = snake_body(payload)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "title": required_text(body.get("title"), "title"),
        "status": "open",
        "restricted": True,
        "legal_hold_id": _hold(store, actor, body.get("legal_hold_id")),
        "opened_at": utcnow(),
    }
    bucket_rows(store, "grc_ethics_cases")[item_id] = row
    record(store, actor, "grc.ethics.opened", item_id, {"title": row["title"]})
    return present(row)


def _hold(store: Any, actor: Actor, value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        hold_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise NotFoundError() from exc
    row = bucket(store, "holds").get(hold_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()
    return hold_id

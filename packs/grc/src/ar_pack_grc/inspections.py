"""A regulator room is one binder and one external guest grant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.identity.guests import GuestBook
from ar_domain.records.access import require
from ar_domain.records.binders import BinderBook
from ar_pack_grc.access import page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import required_text, when

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def list_inspections(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.inspections:manage")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_inspections").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def open_inspection(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.inspections:manage")
    body = snake_body(payload)
    regulator = required_text(body.get("regulator"), "regulator")
    started = when(body.get("started_on"), required=True)
    book = BinderBook(store)
    created = book.create(actor, {"title": f"Inspection {regulator}", "selection": {}})
    binder_id = created.get("id")
    book.build(actor, _as_uuid(binder_id))
    guest = GuestBook(store).invite(
        actor,
        {
            "email": _email(regulator),
            "display_name": regulator,
            "kind": "external",
            "grants": [
                {
                    "portal": "auditor",
                    "scope": {
                        "binder_ids": [str(binder_id)],
                        "evidence_ids": [],
                        "pack_record_ids": [],
                    },
                }
            ],
        },
    )
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "regulator": regulator,
        "started_on": started.date() if started is not None else None,
        "status": "announced",
        "binder_id": binder_id,
        "guest_id": guest.get("id"),
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_inspections")[item_id] = row
    record(store, actor, "grc.inspection.opened", item_id, {"regulator": regulator})
    return present(row)


def _email(regulator: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in regulator).strip("-")
    return f"inspector+{slug or 'regulator'}@example.com"


def _as_uuid(value: object) -> Any:
    import uuid  # noqa: PLC0415

    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))

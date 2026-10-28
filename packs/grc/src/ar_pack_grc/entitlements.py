"""IdP entitlement ingest. A second ingest of the same tuple updates the row."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import as_uuid, choice

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_SOURCES = frozenset({"okta", "entra", "google"})


def list_entitlements(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.campaigns:read")
    body = snake_body(query)
    source = str(body.get("source") or "")
    subject = str(body.get("subject") or "")
    items = []
    for row in bucket_rows(store, "grc_entitlements").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if source and str(row.get("source")) != source:
            continue
        if subject and str(row.get("subject")) != subject:
            continue
        items.append(present(row))
    return page(items)


def ingest(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.campaigns:manage")
    body = snake_body(payload)
    source = choice(body.get("source"), _SOURCES, "source")
    connection_id = as_uuid(body.get("connection_id"))
    rows = _snapshot(store, connection_id)
    seen: set[tuple[str, str]] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()
        entitlement = str(item.get("entitlement") or "").strip()
        if not subject or not entitlement or (subject, entitlement) in seen:
            continue
        seen.add((subject, entitlement))
        _upsert(store, actor, source, subject, entitlement)
    kept = len(seen)
    record(
        store,
        actor,
        "grc.entitlement.ingested",
        connection_id,
        {"source": source, "count": kept},
    )
    return {"source": source, "connection_id": str(connection_id), "count": kept}


def _snapshot(store: Any, connection_id: object) -> list[object]:
    snap = bucket_rows(store, "grc_idp_snapshots").get(connection_id)
    if isinstance(snap, dict) and isinstance(snap.get("items"), list):
        return list(snap["items"])
    connections = getattr(store, "connections", None)
    if isinstance(connections, dict):
        row = connections.get(connection_id)
        if isinstance(row, dict) and isinstance(row.get("entitlements"), list):
            return list(row["entitlements"])
    raise NotFoundError()


def _upsert(store: Any, actor: Actor, source: str, subject: str, entitlement: str) -> None:
    table = bucket_rows(store, "grc_entitlements")
    for row in table.values():
        if (
            same_tenant(row, actor.tenant_id)
            and row.get("source") == source
            and row.get("subject") == subject
            and row.get("entitlement") == entitlement
        ):
            row["collected_at"] = utcnow()
            return
    item_id = new_id()
    table[item_id] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "source": source,
        "subject": subject,
        "entitlement": entitlement,
        "collected_at": utcnow(),
        "evidence_item_id": None,
    }

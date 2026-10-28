"""Regulator feeds, fetched changes and the CSCRF sampling rule."""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from ar_common.errors import ForbiddenError, ValidationFailedError
from ar_common.http import assert_public_url
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import required_text, string_list

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

Getter = Callable[[str], tuple[int, str]]
_COLLECTION = "grc-regulatory"


def list_obligations(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.obligations:read")
    body = snake_body(query)
    regulator = str(body.get("regulator") or "")
    status = str(body.get("status") or "")
    items = []
    for row in bucket_rows(store, "grc_obligations").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if regulator and str(row.get("regulator")) != regulator:
            continue
        if status and str(row.get("status")) != status:
            continue
        items.append(present(row))
    return page(items)


def create_obligation(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.obligations:manage")
    body = snake_body(payload)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "regulator": required_text(body.get("regulator"), "regulator"),
        "citation": required_text(body.get("citation"), "citation"),
        "statement": required_text(body.get("statement"), "statement"),
        "status": "active",
        "owner_user_id": body.get("owner_user_id"),
    }
    bucket_rows(store, "grc_obligations")[item_id] = row
    return present(row)


def patch_obligation(
    store: Any, actor: Actor, obligation_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.obligations:manage")
    row = one(store, "grc_obligations", actor, obligation_id)
    body = snake_body(payload)
    for field in ("regulator", "citation", "statement", "status"):
        if field in body:
            row[field] = required_text(body.get(field), field)
    if "owner_user_id" in body:
        row["owner_user_id"] = body.get("owner_user_id")
    record(store, actor, "grc.obligation.updated", obligation_id, {"citation": row.get("citation")})
    return present(row)


def search_obligations(
    store: Any, actor: Actor, query: str, regulator: str
) -> list[dict[str, Any]]:
    require(actor, "grc.obligations:read")
    found = []
    for row in bucket_rows(store, "grc_obligations").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if regulator and str(row.get("regulator")) != regulator:
            continue
        text = f"{row.get('citation')} {row.get('statement')}".lower()
        if query and query.lower() not in text:
            continue
        found.append(present(row))
    return found


def list_feeds(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.obligations:read")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_regulator_feeds").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def create_feed(
    store: Any,
    actor: Actor,
    payload: dict[str, Any],
    *,
    resolver: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    require(actor, "grc.obligations:manage")
    body = snake_body(payload)
    url = required_text(body.get("url"), "url")
    _public(url, resolver)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "regulator": required_text(body.get("regulator"), "regulator"),
        "url": url,
        "enabled": True,
    }
    bucket_rows(store, "grc_regulator_feeds")[item_id] = row
    return present(row)


def list_changes(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.obligations:read")
    body = snake_body(query)
    status = str(body.get("status") or "")
    items = []
    for row in bucket_rows(store, "grc_regulatory_changes").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if status and str(row.get("status")) != status:
            continue
        items.append(present(row))
    return page(items)


def fetch_feed(
    store: Any,
    actor: Actor,
    feed_id: uuid.UUID,
    *,
    getter: Getter,
    resolver: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    """Store one page as a knowledge document and one change row. robots.txt stops the fetch."""
    require(actor, "grc.obligations:manage")
    feed = one(store, "grc_regulator_feeds", actor, feed_id)
    url = str(feed.get("url") or "")
    _public(url, resolver)
    if _robots_block(url, getter):
        raise ForbiddenError("robots_denied")
    status, text = getter(url)
    if status >= 400 or not text.strip():
        raise ValidationFailedError("the feed page was empty")
    title = _title(text, str(feed.get("regulator") or "Circular"))
    document_id = _document(store, actor, title, url, text)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "feed_id": feed_id,
        "title": title,
        "url": url,
        "body": text,
        "document_id": document_id,
        "status": "new",
        "note": "",
        "obligation_ids": [],
        "control_ids": [],
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_regulatory_changes")[item_id] = row
    return present(row)


def triage(
    store: Any, actor: Actor, change_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.obligations:manage")
    row = one(store, "grc_regulatory_changes", actor, change_id)
    body = snake_body(payload)
    relevant = body.get("relevant") is True
    obligation_ids = string_list(body.get("obligation_ids"))
    control_ids = string_list(body.get("control_ids"))
    for raw in obligation_ids:
        one(store, "grc_obligations", actor, uuid.UUID(raw))
    row["status"] = "triaged" if relevant else "dismissed"
    row["obligation_ids"] = obligation_ids
    row["control_ids"] = control_ids
    row["note"] = str(body.get("note") or "")
    record(
        store,
        actor,
        "grc.regulatory_change.triaged",
        change_id,
        {"relevant": relevant, "obligation_ids": obligation_ids},
    )
    return present(row)


def classify_circular(text: str) -> dict[str, Any]:
    """Classify a circular, including a Hindi DPDP notice."""
    hindi = any(token in text for token in ("डेटा", "उल्लंघन", "घंटे"))
    lowered = text.casefold()
    dpdp = hindi or "personal data" in lowered or "dpdp" in lowered
    cert = "cert-in" in lowered or "six hours" in lowered or "6 घंटे" in text
    regulator = "DPDP" if dpdp else "CERT-In" if cert else "other"
    citations = []
    if dpdp:
        citations.append("Rules 2025 rule 7")
    if cert:
        citations.append("Directions 2022 para ii")
    return {
        "language": "hi" if hindi else "en",
        "regulator": regulator,
        "relevant": bool(citations),
        "obligation_citations": citations,
    }


def sample_size(population: int) -> int:
    """CSCRF sample. Up to 25 is everything. Above that, at least 25 percent rounded up."""
    if population < 0:
        raise ValidationFailedError("population is invalid")
    if population <= 25:
        return population
    return math.ceil(population * 0.25)


def _public(url: str, resolver: Callable[[str], list[str]] | None) -> None:
    if resolver is None:
        assert_public_url(url)
        return
    assert_public_url(url, resolver=resolver)


def _robots_block(url: str, getter: Getter) -> bool:
    parsed = urlparse(url)
    robots = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    status, text = getter(robots)
    if status == 404:
        return False
    path = parsed.path or "/"
    agent = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        name = key.strip().lower()
        rule = value.strip()
        if name == "user-agent":
            agent = rule == "*"
            continue
        if agent and name == "disallow" and rule in {"/", path}:
            return True
    return False


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:180]
    return fallback


def _document(store: Any, actor: Actor, title: str, url: str, text: str) -> uuid.UUID:
    collection = _collection(store, actor)
    document_id = new_id()
    store.knowledge_documents[document_id] = {
        "id": document_id,
        "tenant_id": actor.tenant_id,
        "collection_id": collection,
        "title": title,
        "source_url": url,
        "status": "ready",
        "pack_owned": True,
        "created_at": utcnow(),
    }
    store.knowledge_blobs[document_id] = text.encode()
    return document_id


def _collection(store: Any, actor: Actor) -> uuid.UUID:
    for row in store.knowledge_collections.values():
        if row.get("tenant_id") == actor.tenant_id and row.get("slug") == _COLLECTION:
            found = row.get("id")
            if isinstance(found, uuid.UUID):
                return found
    collection_id = new_id()
    store.knowledge_collections[collection_id] = {
        "id": collection_id,
        "tenant_id": actor.tenant_id,
        "slug": _COLLECTION,
        "name": "GRC regulatory",
        "visibility": "tenant",
        "pack_owned": True,
        "created_by": actor.user_id,
        "created_at": utcnow(),
    }
    return collection_id

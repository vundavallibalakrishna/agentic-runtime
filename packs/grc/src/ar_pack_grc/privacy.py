"""DSAR and consent. Erasure uses the core workflow and skips held evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.holds import HoldBook, is_held
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import open_review, signed_for
from ar_pack_grc.values import as_uuid, choice, required_text, when

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_TYPES = frozenset({"access", "correction", "erasure", "portability"})
_STATES = frozenset({"granted", "withdrawn"})


def list_requests(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.privacy:manage")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_dsar_requests").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def create_request(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.privacy:manage")
    body = snake_body(payload)
    request_type = choice(body.get("request_type"), _TYPES, "request_type")
    due_at = when(body.get("due_at"), required=True)
    subject = as_uuid(body.get("subject_user_id"), required=False)
    item_id = new_id()
    row: dict[str, Any] = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "request_type": request_type,
        "due_at": due_at,
        "status": "open",
        "subject_user_id": subject,
        "evidence_item_id": None,
        "held_record_ids": [],
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_dsar_requests")[item_id] = row
    if request_type == "erasure":
        statement = f"Erase platform records for {subject or 'the subject'}."
        review = open_review(
            store,
            actor,
            slug="grc-dsar",
            subject_id=item_id,
            content=statement,
            statement=statement,
        )
        row["content_hash"] = review.get("content_hash")
    return present(row)


def fulfil(store: Any, actor: Actor, request_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.privacy:manage")
    row = one(store, "grc_dsar_requests", actor, request_id)
    if row.get("status") == "fulfilled":
        return present(row)
    if row.get("request_type") == "erasure":
        digest = str(row.get("content_hash") or "")
        if signed_for(store, row["id"], digest) is None:
            raise ConflictError("review_required")
        subject = row.get("subject_user_id")
        if subject is not None:
            row["held_record_ids"] = _erase(store, actor, subject)
    row["status"] = "fulfilled"
    record(store, actor, "grc.dsar.fulfilled", row["id"], {"request_type": row.get("request_type")})
    return present(row)


def list_consent(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.privacy:manage")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_consent_records").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def record_consent(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.privacy:manage")
    body = snake_body(payload)
    evidence_id = as_uuid(body.get("evidence_item_id"), required=False)
    if evidence_id is None or not _evidence(store, actor, evidence_id):
        raise ValidationFailedError("evidence is required")
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "subject_ref": required_text(body.get("subject_ref"), "subject_ref"),
        "purpose": required_text(body.get("purpose"), "purpose"),
        "state": choice(body.get("state"), _STATES, "state"),
        "evidence_item_id": evidence_id,
        "recorded_at": utcnow(),
    }
    bucket_rows(store, "grc_consent_records")[item_id] = row
    record(store, actor, "grc.consent.recorded", item_id, {"state": row["state"]})
    return present(row)


def _erase(store: Any, actor: Actor, subject: object) -> list[str]:
    import uuid  # noqa: PLC0415

    user_id = subject if isinstance(subject, uuid.UUID) else uuid.UUID(str(subject))
    result = HoldBook(store).erase(actor, user_id)
    raw_held = result.get("held_record_ids")
    held = [str(item) for item in raw_held] if isinstance(raw_held, list) else []
    evidence = bucket(store, "evidence")
    for item_id, item in list(evidence.items()):
        if not isinstance(item, dict) or not same_tenant(item, actor.tenant_id):
            continue
        owner = item.get("collector_principal_id") or item.get("user_id")
        if str(owner or "") != str(user_id):
            continue
        if is_held(store, "evidence_item", item_id) or item.get("legal_hold") is True:
            held.append(str(item_id))
            continue
        evidence.pop(item_id, None)
    return held


def _evidence(store: Any, actor: Actor, evidence_id: uuid.UUID) -> bool:
    row = bucket(store, "evidence").get(evidence_id)
    return isinstance(row, dict) and same_tenant(row, actor.tenant_id)

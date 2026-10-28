"""Pack records use the core review queue. Sign-off is not decided here."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, cast

from ar_common.time import utcnow
from ar_domain.approvals.reviews import ReviewBook

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_OPEN = frozenset({"pending", "in_review"})


def bind(store: Any, subject_id: uuid.UUID, content: str) -> str:
    """Store the bytes the core hash reads, and return that hash."""
    raw = content.encode()
    store.blobs[subject_id] = raw
    return hashlib.sha256(raw).hexdigest()


def current_hash(store: Any, subject_id: uuid.UUID) -> str:
    extra = store.blobs.get(subject_id)
    if isinstance(extra, bytes) and extra:
        return hashlib.sha256(extra).hexdigest()
    return hashlib.sha256(f"pack_record:{subject_id}".encode()).hexdigest()


def ensure_queue(store: Any, actor: Actor, slug: str) -> dict[str, Any]:
    for row in store.review_queues.values():
        if row.get("tenant_id") == actor.tenant_id and row.get("slug") == slug:
            return cast("dict[str, Any]", row)
    created = ReviewBook(store).create_queue(
        actor,
        {
            "slug": slug,
            "name": slug,
            "subject_type": "pack_record",
            "levels": [{"level": 1, "required_count": 1, "step_up": False, "role_key": ""}],
        },
    )
    queue_id = created.get("id")
    saved = store.review_queues.get(queue_id)
    return saved if isinstance(saved, dict) else {}


def open_review(
    store: Any,
    actor: Actor,
    *,
    slug: str,
    subject_id: uuid.UUID,
    content: str,
    statement: str,
) -> dict[str, Any]:
    digest = bind(store, subject_id, content)
    queue = ensure_queue(store, actor, slug)
    return ReviewBook(store).open_item(
        actor,
        {
            "queue_id": queue["id"],
            "subject_type": "pack_record",
            "subject_id": subject_id,
            "subject_ref": {},
            "content_hash": digest,
            "statement_text": statement,
        },
    )


def supersede(store: Any, subject_id: uuid.UUID, content: str) -> str:
    """A new hash retires every open review of this record."""
    digest = bind(store, subject_id, content)
    for row in store.review_items.values():
        if row.get("subject_id") != subject_id or row.get("status") not in _OPEN:
            continue
        if row.get("content_hash") == digest:
            continue
        row["status"] = "superseded"
        row["updated_at"] = utcnow()
    return digest


def signed_for(store: Any, subject_id: uuid.UUID, digest: str) -> dict[str, Any] | None:
    for row in store.review_items.values():
        if row.get("subject_id") != subject_id:
            continue
        if row.get("status") == "signed" and row.get("content_hash") == digest:
            return cast("dict[str, Any]", row)
    return None


def audited(store: Any, action: str, target_id: object) -> bool:
    return any(
        row.get("action") == action and str(row.get("target_id")) == str(target_id)
        for row in store.audit_log
    )

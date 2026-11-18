"""Accepting an assistant reply. Spec: docs/03-specs/09-policy-approvals.md §11.1.

A reply is AI-generated and not reviewed until a named person accepts it. The record of
acceptance is a signed review item whose subject is the message, so the signer, the time
and the hash of the exact text are the ones the sign-off mechanism already keeps.
"""

import hashlib
import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import (
    ArError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    ValidationFailedError,
)
from ar_domain.approvals.reviews import ReviewBook
from ar_domain.identity.tenant_settings import section, settings_for
from ar_domain.rows import as_datetime, as_int, as_uuid_or_none

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_OPEN = frozenset({"pending", "in_review"})
_STATUS = {
    "pending": "in_review",
    "in_review": "in_review",
    "signed": "accepted",
    "rejected": "rejected",
}
_NOT_SET_UP = (
    "Reply acceptance is not set up. An administrator chooses the review queue for "
    "replies in the tenant settings (approvals.replyReviewQueueId)."
)


def reply_queue_id(store: Any, tenant_id: object) -> uuid.UUID | None:
    """The queue the tenant chose for accepting replies, or None when it chose none."""
    chosen = section(settings_for(store, tenant_id), "approvals").get("reply_review_queue_id")
    return _uuid(chosen)


def reply_queue(store: Any, tenant_id: object) -> dict[str, object] | None:
    """The chosen queue when it still exists, belongs to the tenant and reviews messages."""
    row = store.review_queues.get(reply_queue_id(store, tenant_id))
    if (
        not isinstance(row, dict)
        or str(row.get("tenant_id")) != str(tenant_id)
        or row.get("subject_type") != "message"
    ):
        return None
    return row


def check_queue_setting(store: Any, tenant_id: object, patch: dict[str, object] | None) -> None:
    """Refuse a settings change that names a queue replies cannot be accepted in."""
    approvals = (patch or {}).get("approvals")
    if not isinstance(approvals, dict):
        return
    keys = ("replyReviewQueueId", "reply_review_queue_id")
    named = [approvals[key] for key in keys if key in approvals]
    if not named or named[0] is None or named[0] == "":
        return
    row = store.review_queues.get(_uuid(named[0]))
    if not isinstance(row, dict) or str(row.get("tenant_id")) != str(tenant_id):
        raise ValidationFailedError(
            "approvals.replyReviewQueueId does not name a review queue of this tenant."
        )
    if row.get("subject_type") != "message":
        raise ValidationFailedError(
            "approvals.replyReviewQueueId must name a review queue whose subject type is message."
        )


def attach_reviews(store: Any, actor: Actor | None, messages: list[dict[str, object]]) -> None:
    """Put ``review`` on each assistant message of one conversation view."""
    replies = [row for row in messages if row.get("role") == "assistant"]
    if not replies:
        return
    by_subject: dict[str, list[dict[str, object]]] = {}
    for item in store.review_items.values():
        if item.get("subject_type") == "message":
            by_subject.setdefault(str(item.get("subject_id")), []).append(item)
    queue = None if actor is None else reply_queue(store, actor.tenant_id)
    for row in replies:
        raw = store.messages.get(_uuid(row.get("id")))
        if isinstance(raw, dict):
            row["review"] = _state(store, actor, raw, queue, by_subject.get(str(raw["id"]), []))


def reply_review(store: Any, actor: Actor | None, message: dict[str, object]) -> dict[str, object]:
    """The review state of one stored assistant message, as the API returns it."""
    items = [
        item
        for item in store.review_items.values()
        if item.get("subject_type") == "message" and item.get("subject_id") == message["id"]
    ]
    queue = None if actor is None else reply_queue(store, actor.tenant_id)
    return _state(store, actor, message, queue, items)


def accept_reply(
    store: Any,
    actor: Actor,
    message: dict[str, object],
    *,
    statement: str | None,
    comment: str,
    stepped_up: bool,
) -> dict[str, object]:
    """Record that the caller reviewed this exact reply and accepts it.

    ``message`` is a stored message the caller is allowed to read. Every check runs before
    anything is written, so a refused acceptance leaves no open item behind. Accepting a
    reply that is already accepted changes nothing.
    """
    if message.get("role") != "assistant":
        raise ValidationFailedError("Only an assistant reply can be accepted.")
    if "reviews:decide" not in actor.permissions:
        raise ForbiddenError()
    queue = reply_queue(store, actor.tenant_id)
    if queue is None:
        raise ArError(ErrorCode.INVALID_STATE, _NOT_SET_UP)
    if message.get("status") != "completed" or not str(message.get("text") or ""):
        raise ArError(
            ErrorCode.INVALID_STATE,
            "Only a finished reply can be accepted. Wait for the answer, or ask again.",
        )
    book = ReviewBook(store)
    current = _current(store, message)
    if current is not None and current.get("status") == "signed":
        return reply_review(store, actor, message)
    if current is not None and current.get("status") in _OPEN:
        row = current
        if statement and statement != row.get("statement_text"):
            raise ConflictError(
                "A review of this reply is already open with a different statement. "
                "Accept it without a statement, or decide the open review item."
            )
        filed = True
    else:
        row = _draft(store, book, actor, queue, message, statement)
        filed = False
    book.assert_may_sign(actor, row)
    book.assert_cleared(actor, row, "approve", stepped_up=stepped_up)
    if not filed:
        book.file(actor, row)
    book.decide(
        actor,
        uuid.UUID(str(row["id"])),
        {
            "decision": "approve",
            "comment": comment,
            "content_hash": row["content_hash"],
            "statement_hash": row["statement_hash"],
        },
        stepped_up=stepped_up,
    )
    return reply_review(store, actor, message)


def _draft(  # noqa: PLR0917
    store: Any,
    book: ReviewBook,
    actor: Actor,
    queue: dict[str, object],
    message: dict[str, object],
    statement: str | None,
) -> dict[str, object]:
    """An unfiled review item for the reply, prepared by the agent that wrote it."""
    run = store.runs.get(message.get("run_id"))
    agent_id = run.get("agent_id") if isinstance(run, dict) else None
    if not isinstance(agent_id, uuid.UUID):
        raise ArError(
            ErrorCode.INVALID_STATE,
            "This reply has no agent on record, so it cannot be accepted.",
        )
    digest = _digest(message)
    return book.draft(
        actor,
        queue,
        subject_type="message",
        subject_id=uuid.UUID(str(message["id"])),
        subject_ref={},
        statement=statement or _statement(store, queue, message, digest),
        preparer=("agent", agent_id),
    )


def _statement(
    store: Any, queue: dict[str, object], message: dict[str, object], digest: str
) -> str:
    """The queue's statement, with the conversation title and the hash filled in."""
    conversation = store.conversations.get(message.get("conversation_id"))
    title = conversation.get("title") if isinstance(conversation, dict) else None
    template = str(queue.get("statement_template") or "")
    return template.replace("{title}", str(title or message["id"])).replace(
        "{content_hash}", digest
    )


def _digest(message: dict[str, object]) -> str:
    return hashlib.sha256(str(message.get("text") or "").encode()).hexdigest()


def _current(store: Any, message: dict[str, object]) -> dict[str, object] | None:
    items = [
        item
        for item in store.review_items.values()
        if item.get("subject_type") == "message" and item.get("subject_id") == message["id"]
    ]
    return _latest(items, message)


def _latest(items: list[dict[str, object]], message: dict[str, object]) -> dict[str, object] | None:
    """The newest review of the reply as it reads now. A review of older text does not count."""
    digest = _digest(message)
    live = [
        item
        for item in items
        if item.get("tenant_id") == message.get("tenant_id")
        and item.get("content_hash") == digest
        and item.get("status") in _STATUS
    ]
    return max(live, key=lambda item: str(item.get("created_at")), default=None)


def _state(
    store: Any,
    actor: Actor | None,
    message: dict[str, object],
    queue: dict[str, object] | None,
    items: list[dict[str, object]],
) -> dict[str, object]:
    item = _latest(items, message)
    status = "unreviewed" if item is None else _STATUS[str(item.get("status"))]
    signed = _final_signoff(store, item) if item is not None and status == "accepted" else None
    accepted_at = None if signed is None else as_datetime(signed.get("created_at"))
    return {
        "status": status,
        "accepted_by": None
        if signed is None
        else {
            "id": str(signed.get("signer_principal_id")),
            "name": _name(store, signed.get("signer_principal_id")),
        },
        "accepted_at": None if accepted_at is None else accepted_at.isoformat(),
        "content_hash": _digest(message),
        "review_item_id": None if item is None else str(item.get("id")),
        "can_accept": _can_accept(store, actor, message, queue, item),
    }


def _can_accept(
    store: Any,
    actor: Actor | None,
    message: dict[str, object],
    queue: dict[str, object] | None,
    item: dict[str, object] | None,
) -> bool:
    """Whether Accept is offered: set up, finished, not yet accepted, and the caller may sign."""
    if actor is None or queue is None or "reviews:decide" not in actor.permissions:
        return False
    if message.get("status") != "completed" or not str(message.get("text") or ""):
        return False
    book = ReviewBook(store)
    if item is not None and item.get("status") in _OPEN:
        return book.may_sign(actor, item)
    if item is not None and item.get("status") == "signed":
        return False
    try:
        return book.may_sign(actor, _draft(store, book, actor, queue, message, None))
    except ArError:
        return False


def _final_signoff(store: Any, item: dict[str, object]) -> dict[str, object] | None:
    """The approval that completed the last level: the person the acceptance is credited to."""
    approvals = [
        sign
        for sign in store.signoffs.values()
        if sign.get("review_item_id") == item.get("id") and sign.get("decision") == "approve"
    ]
    return max(
        approvals,
        key=lambda sign: (as_int(sign.get("level")), str(sign.get("created_at"))),
        default=None,
    )


def _uuid(value: object) -> uuid.UUID | None:
    """A stored or submitted id, or None when it is empty or is not an id."""
    try:
        return as_uuid_or_none(value)
    except ValueError:
        return None


def _name(store: Any, user_id: object) -> str:
    names = getattr(store, "display_names", {})
    emails = getattr(store, "user_emails", {})
    return str(names.get(user_id) or emails.get(user_id) or "")

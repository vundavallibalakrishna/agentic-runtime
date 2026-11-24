"""Tell the approvers, outside the console, that a decision is waiting.

Cards go to Slack and Teams bindings. Mail goes to each approver's address.
A configured extra address (``AR_APPROVAL_NOTIFY_EMAIL``) is added when set.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

from ar_domain.channels.cards import links_for, post_cards
from ar_domain.notifications.smtp_mail import send_install_mail
from ar_domain.webhooks.delivery import dispatch_public_event

if TYPE_CHECKING:
    from typing import Any


def announce(store: Any, row: dict[str, object], approver_ids: list[str]) -> None:
    """Cards, mail and the ``approval.requested`` webhook. Failures are recorded, not raised."""
    links = links_for(store, row, approver_ids)
    try:
        post_cards(store, row, approver_ids, links)
    except Exception:  # noqa: BLE001 — a card failure must not lose the approval
        links = links or {}
    _mail(store, row, approver_ids, links)
    tenant_id = row.get("tenant_id")
    dispatch_public_event(
        store,
        tenant_id,
        "approval.requested",
        {
            "approval_id": str(row.get("id") or ""),
            "run_id": None if row.get("run_id") is None else str(row.get("run_id")),
            "qualified_name": str(row.get("qualified_name") or ""),
            "approver_user_ids": approver_ids,
        },
    )


def approver_emails(store: Any, approver_ids: list[str]) -> list[str]:
    """Addresses of the approvers, plus the install's extra recipient when one is set."""
    book = getattr(store, "user_emails", {})
    found: list[str] = []
    if isinstance(book, dict):
        for user_id in approver_ids:
            email = book.get(user_id) or book.get(_as_uuid(user_id))
            text = str(email or "").strip()
            if text and text not in found:
                found.append(text)
    extra = os.environ.get("AR_APPROVAL_NOTIFY_EMAIL", "").strip()
    if extra and extra not in found:
        found.append(extra)
    return found


def _mail(
    store: Any, row: dict[str, object], approver_ids: list[str], links: dict[str, str]
) -> None:
    name = str(row.get("qualified_name") or "a tool")
    shared = next(iter(links.values()), "")
    for email in approver_emails(store, approver_ids):
        user_id = _user_for_email(store, email)
        link = links.get(user_id, shared)
        body = f"A run is waiting on {name}."
        if link:
            body = f"{body}\n\nReview: {link}"
        send_install_mail(email, "Approval requested", body)


def _user_for_email(store: Any, email: str) -> str:
    book = getattr(store, "user_emails", {})
    if not isinstance(book, dict):
        return ""
    for key, value in book.items():
        if str(value).lower() == email.lower():
            return str(key)
    return ""


def _as_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None

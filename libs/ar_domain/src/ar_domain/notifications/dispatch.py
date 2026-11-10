"""Web push subscriptions and email notices.

Push delivery signs a VAPID JWT with the named secret ``web_push_vapid_private``.
Without a usable key the subscription is stored and the send stays pending.
A 404 or 410 drops that subscription. Email is queued for the SMTP activity.
"""

from __future__ import annotations

import uuid
from typing import Any  # noqa: TC003

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.identity.recovery import deliver
from ar_domain.notifications.web_push import load_private_key, post_push
from ar_domain.tools.named_secrets import read_named_secret


def subscribe(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    endpoint: str,
    encoding: str = "aes128gcm",
) -> dict[str, object]:
    book = _book(store)
    for row in book.values():
        if row.get("tenant_id") == tenant_id and row.get("endpoint") == endpoint:
            row["user_id"] = user_id
            row["content_encoding"] = encoding or "aes128gcm"
            row["updated_at"] = utcnow()
            return _public(row)
    row_id = new_id()
    row = {
        "id": row_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "endpoint": endpoint,
        "content_encoding": encoding or "aes128gcm",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    book[row_id] = row
    return _public(row)


def unsubscribe(store: Any, *, tenant_id: uuid.UUID, subscription_id: uuid.UUID) -> bool:
    book = _book(store)
    row = book.get(subscription_id)
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        return False
    del book[subscription_id]
    return True


def notify_user(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    body: str,
    email: str = "",
) -> dict[str, object]:
    """Send a Web Push where a VAPID key exists, and queue an email for SMTP."""
    secret = read_named_secret(store, tenant_id, "web_push_vapid_private")
    targets = [
        row
        for row in list(_book(store).values())
        if row.get("tenant_id") == tenant_id and row.get("user_id") == user_id
    ]
    key = load_private_key(secret) if secret else None
    delivered = 0
    pruned = 0
    if key is not None:
        transport = getattr(store, "push_transport", None)
        for row in targets:
            endpoint = str(row.get("endpoint") or "")
            status = post_push(endpoint, title, body, key, transport=transport)
            if status in {404, 410}:
                row_id = row.get("id")
                if isinstance(row_id, uuid.UUID):
                    unsubscribe(store, tenant_id=tenant_id, subscription_id=row_id)
                pruned += 1
            elif 200 <= status < 300:
                delivered += 1
    push = {
        "attempted": len(targets),
        "delivered": delivered,
        "pruned": pruned,
        "proof": "contract" if key is not None else "unit",
        "pending": key is None,
    }
    if email:
        deliver(store, {"to": email, "subject": title, "body": body})
    return {"push": push, "email": bool(email)}


def _book(store: Any) -> dict[object, dict[str, object]]:
    current = getattr(store, "push_subscriptions", None)
    if not isinstance(current, dict):
        current = {}
        store.push_subscriptions = current
    return current


def _public(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "endpoint": row.get("endpoint"),
        "contentEncoding": row.get("content_encoding"),
    }

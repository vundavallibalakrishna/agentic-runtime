"""Tenant outbound webhooks on the tables the schema already has.

Subscriptions and deliveries live on the store (``outbound_webhooks``,
``webhook_deliveries``, ``outbox_events``) and flush with the other durable
rows. The signing secret is a named secret. It is returned once, on create and
on rotate, and is not on the public row.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_contracts.events import PUBLIC_TOPICS
from ar_domain.tools.named_secrets import read_named_secret, write_named_secret

_STATUSES = frozenset({"active", "disabled", "failing"})


def _bucket(store: Any, name: str) -> dict[Any, dict[str, object]]:
    found = getattr(store, name, None)
    if not isinstance(found, dict):
        found = {}
        setattr(store, name, found)
    return found


def _public(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if key != "secret_name"}


class WebhookBook:
    """CRUD and a delivery log for one tenant."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_hooks(self, tenant_id: uuid.UUID) -> list[dict[str, object]]:
        return [
            _public(row)
            for row in _bucket(self.store, "outbound_webhooks").values()
            if row.get("tenant_id") == tenant_id
        ]

    def get(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> dict[str, object]:
        return _public(self._own(tenant_id, webhook_id))

    def create(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        name: str,
        url: str,
        topics: list[str],
    ) -> dict[str, object]:
        cleaned = _topics(topics)
        _require_https(url)
        if any(
            row.get("tenant_id") == tenant_id and row.get("name") == name
            for row in _bucket(self.store, "outbound_webhooks").values()
        ):
            raise ConflictError("a webhook with that name already exists")
        webhook_id = new_id()
        secret = _new_secret()
        secret_name = f"webhook:{webhook_id}"
        write_named_secret(self.store, tenant_id, secret_name, secret)
        now = utcnow()
        row: dict[str, object] = {
            "id": webhook_id,
            "tenant_id": tenant_id,
            "name": name,
            "url": url,
            "secret_ref_id": None,
            "secret_name": secret_name,
            "topics": cleaned,
            "status": "active",
            "created_by": user_id,
            "created_at": now,
            "updated_at": now,
        }
        _bucket(self.store, "outbound_webhooks")[webhook_id] = row
        shown = _public(row)
        shown["secret"] = secret
        return shown

    def update(  # noqa: PLR0917
        self,
        tenant_id: uuid.UUID,
        webhook_id: uuid.UUID,
        name: str,
        url: str,
        topics: list[str],
        status: str = "",
    ) -> dict[str, object]:
        row = self._own(tenant_id, webhook_id)
        _require_https(url)
        if status and status not in _STATUSES:
            raise ValidationFailedError("status must be active, disabled or failing")
        row["name"] = name
        row["url"] = url
        row["topics"] = _topics(topics)
        if status:
            row["status"] = status
        row["updated_at"] = utcnow()
        return _public(row)

    def delete(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> bool:
        row = _bucket(self.store, "outbound_webhooks").get(webhook_id)
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            return False
        _bucket(self.store, "outbound_webhooks").pop(webhook_id, None)
        deliveries = _bucket(self.store, "webhook_deliveries")
        for key, item in list(deliveries.items()):
            if item.get("webhook_id") == webhook_id:
                deliveries.pop(key, None)
        return True

    def rotate(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> str:
        row = self._own(tenant_id, webhook_id)
        secret = _new_secret()
        name = str(row.get("secret_name") or f"webhook:{webhook_id}")
        row["secret_name"] = name
        write_named_secret(self.store, tenant_id, name, secret)
        row["updated_at"] = utcnow()
        return secret

    def secret(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> str:
        row = self._own(tenant_id, webhook_id)
        found = read_named_secret(self.store, tenant_id, str(row.get("secret_name") or ""))
        return found or ""

    def deliveries(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> list[dict[str, object]]:
        self._own(tenant_id, webhook_id)
        rows = [
            _delivery_public(self.store, item)
            for item in _bucket(self.store, "webhook_deliveries").values()
            if item.get("webhook_id") == webhook_id and item.get("tenant_id") == tenant_id
        ]
        rows.sort(key=lambda item: str(item.get("created_at") or ""))
        return rows

    def enqueue(
        self,
        tenant_id: uuid.UUID,
        topic: str,
        payload: dict[str, object],
        *,
        webhook_id: uuid.UUID | None = None,
    ) -> list[dict[str, object]]:
        """One delivery per active subscription of this topic. ``*`` subscribes to all."""
        matched = [
            row
            for row in _bucket(self.store, "outbound_webhooks").values()
            if _wants(row, tenant_id, topic, webhook_id)
        ]
        if not matched:
            return []
        event_id = new_id()
        now = utcnow()
        _bucket(self.store, "outbox_events")[event_id] = {
            "id": event_id,
            "tenant_id": tenant_id,
            "topic": topic,
            "payload": payload,
            "created_at": now,
            "published_at": None,
            "attempts": 0,
        }
        made: list[dict[str, object]] = []
        for row in matched:
            delivery_id = new_id()
            delivery = {
                "id": delivery_id,
                "tenant_id": tenant_id,
                "webhook_id": row.get("id"),
                "target_url": None,
                "outbox_event_id": event_id,
                "status": "pending",
                "attempts": 0,
                "last_status_code": None,
                "last_error": None,
                "next_attempt_at": now,
                "created_at": now,
                "updated_at": now,
            }
            _bucket(self.store, "webhook_deliveries")[delivery_id] = delivery
            made.append(delivery)
        return made

    def redeliver(
        self, tenant_id: uuid.UUID, webhook_id: uuid.UUID, delivery_id: uuid.UUID
    ) -> dict[str, object]:
        """A new attempt row for the same event. The previous row stays as history."""
        row = self.get_delivery(delivery_id)
        if row is None or row.get("webhook_id") != webhook_id or row.get("tenant_id") != tenant_id:
            raise NotFoundError("delivery not found")
        event_id = row.get("outbox_event_id")
        if not isinstance(event_id, uuid.UUID):
            raise NotFoundError("delivery not found")
        if not isinstance(_bucket(self.store, "outbox_events").get(event_id), dict):
            raise NotFoundError("delivery not found")
        now = utcnow()
        delivery_id = new_id()
        delivery = {
            "id": delivery_id,
            "tenant_id": tenant_id,
            "webhook_id": webhook_id,
            "target_url": None,
            "outbox_event_id": event_id,
            "status": "pending",
            "attempts": 0,
            "last_status_code": None,
            "last_error": None,
            "next_attempt_at": now,
            "created_at": now,
            "updated_at": now,
        }
        _bucket(self.store, "webhook_deliveries")[delivery_id] = delivery
        return delivery

    def get_delivery(self, delivery_id: uuid.UUID) -> dict[str, object] | None:
        row = _bucket(self.store, "webhook_deliveries").get(delivery_id)
        return row if isinstance(row, dict) else None

    def _own(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> dict[str, object]:
        row = _bucket(self.store, "outbound_webhooks").get(webhook_id)
        if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
            raise NotFoundError("webhook not found")
        return row


def _wants(
    row: dict[str, object], tenant_id: uuid.UUID, topic: str, webhook_id: uuid.UUID | None
) -> bool:
    if row.get("tenant_id") != tenant_id or row.get("status") != "active":
        return False
    if webhook_id is not None:
        return row.get("id") == webhook_id
    topics = row.get("topics")
    names = topics if isinstance(topics, list) else []
    return "*" in names or topic in names


def _topics(topics: list[str]) -> list[str]:
    if not topics:
        raise ValidationFailedError("a webhook needs at least one topic")
    cleaned = [str(item) for item in topics if str(item)]
    unknown = [item for item in cleaned if item != "*" and item not in PUBLIC_TOPICS]
    if unknown:
        raise ValidationFailedError(f"unknown event topic {unknown[0]}")
    return cleaned


def _require_https(url: str) -> None:
    if not url.startswith("https://"):
        raise ValidationFailedError("a webhook address must start with https://")


def _new_secret() -> str:
    import secrets  # noqa: PLC0415

    return secrets.token_urlsafe(24)


def event_body(store: object, row: dict[str, object]) -> tuple[str, dict[str, object]]:
    """Topic and payload live on the outbox event, not on the delivery row."""
    events = getattr(store, "outbox_events", {})
    event_id = row.get("outbox_event_id")
    event = events.get(event_id) if isinstance(events, dict) else None
    if isinstance(event, dict):
        payload = event.get("payload")
        return str(event.get("topic") or ""), payload if isinstance(payload, dict) else {}
    payload = row.get("payload")
    return str(row.get("topic") or ""), payload if isinstance(payload, dict) else {}


def _delivery_public(store: object, row: dict[str, object]) -> dict[str, object]:
    topic, _payload = event_body(store, row)
    return {
        "id": str(row.get("id")),
        "topic": topic,
        "status": row.get("status"),
        "attempts": row.get("attempts"),
        "last_status_code": row.get("last_status_code"),
        "last_error": row.get("last_error"),
        "created_at": row.get("created_at"),
        "next_attempt_at": row.get("next_attempt_at"),
    }

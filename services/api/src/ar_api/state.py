"""Process-local stand-ins for audit, platform, notifications and webhooks.

Request handlers talk to these ports. Tests replace ``app.state`` fields.
Database-backed adapters are constructed when a session is available.
"""

import secrets
import uuid
from dataclasses import dataclass, field
from typing import cast


@dataclass
class AuditApi:
    events: list[dict[str, object]] = field(default_factory=list)

    async def list_events(self) -> list[dict[str, object]]:
        return list(self.events)

    async def get(self, event_id: int) -> dict[str, object] | None:
        for item in self.events:
            if item.get("id") == event_id:
                return item
        return None

    async def verify(self) -> dict[str, object]:
        return {"ok": True, "checked": len(self.events), "broken_id": None}


@dataclass
class PlatformApi:
    tenants: dict[str, dict[str, object]] = field(default_factory=dict)
    plans: dict[str, dict[str, object]] = field(default_factory=dict)

    async def list_tenants(self) -> list[dict[str, object]]:
        return list(self.tenants.values())

    async def get_tenant(self, tenant_id: str) -> dict[str, object] | None:
        return self.tenants.get(tenant_id)

    async def provision(self, slug: str, name: str, plan_key: str, owner_email: str) -> str:
        tenant_id = str(uuid.uuid4())
        self.tenants[tenant_id] = {
            "id": tenant_id,
            "slug": slug,
            "name": name,
            "plan_key": plan_key,
            "owner_email": owner_email,
            "status": "provisioning",
        }
        return tenant_id

    async def set_status(self, tenant_id: str, status: str) -> None:
        row = self.tenants.get(tenant_id)
        if row is not None:
            row["status"] = status

    async def delete(self, tenant_id: str, confirm_slug: str) -> None:
        row = self.tenants.get(tenant_id)
        if row is None or row.get("slug") != confirm_slug:
            return
        row["status"] = "deleting"

    async def list_plans(self) -> list[dict[str, object]]:
        return list(self.plans.values())

    async def save_plan(
        self, plan_id: str | None, key: str, name: str, limits: dict[str, object]
    ) -> dict[str, object]:
        identifier = plan_id or str(uuid.uuid4())
        row: dict[str, object] = {
            "id": identifier,
            "key": key,
            "name": name,
            "limits": dict(limits),
        }
        self.plans[identifier] = row
        return row


@dataclass
class NotificationApi:
    items: list[dict[str, object]] = field(default_factory=list)

    async def list_items(self) -> list[dict[str, object]]:
        return list(self.items)

    async def read(self, notification_id: str) -> bool:
        for item in self.items:
            if item.get("id") == notification_id:
                item["read"] = True
                return True
        return False

    async def read_all(self) -> int:
        count = 0
        for item in self.items:
            if not item.get("read"):
                item["read"] = True
                count += 1
        return count

    def add(self, title: str, body: str) -> dict[str, object]:
        row = {"id": str(uuid.uuid4()), "title": title, "body": body, "read": False}
        self.items.append(row)
        return row


@dataclass
class WebhookApi:
    rows: dict[str, dict[str, object]] = field(default_factory=dict)
    callback_secret: str = ""

    async def list_hooks(self) -> list[dict[str, object]]:
        return [_public(row) for row in self.rows.values()]

    async def get(self, webhook_id: str) -> dict[str, object] | None:
        row = self.rows.get(webhook_id)
        return None if row is None else _public(row)

    async def create(self, name: str, url: str, topics: list[str]) -> dict[str, object]:
        webhook_id = str(uuid.uuid4())
        self.rows[webhook_id] = {
            "id": webhook_id,
            "name": name,
            "url": url,
            "topics": topics,
            "secret": secrets.token_urlsafe(24),
            "deliveries": [],
        }
        return _public(self.rows[webhook_id])

    async def update(
        self, webhook_id: str, name: str, url: str, topics: list[str]
    ) -> dict[str, object] | None:
        row = self.rows.get(webhook_id)
        if row is None:
            return None
        row["name"] = name
        row["url"] = url
        row["topics"] = topics
        return _public(row)

    async def delete(self, webhook_id: str) -> bool:
        return self.rows.pop(webhook_id, None) is not None

    async def rotate(self, webhook_id: str) -> str | None:
        row = self.rows.get(webhook_id)
        if row is None:
            return None
        secret = secrets.token_urlsafe(24)
        row["secret"] = secret
        return secret

    async def enqueue_test(self, webhook_id: str) -> None:
        row = self.rows.get(webhook_id)
        if row is None:
            return
        deliveries = row["deliveries"]
        if isinstance(deliveries, list):
            deliveries.append({"id": str(uuid.uuid4()), "status": "pending"})

    async def deliveries(self, webhook_id: str) -> list[object]:
        row = self.rows.get(webhook_id)
        if row is None:
            return []
        found = row["deliveries"]
        return list(found) if isinstance(found, list) else []

    async def redeliver(self, delivery_id: str) -> None:
        del delivery_id

    async def rotate_callback(self) -> str:
        self.callback_secret = secrets.token_urlsafe(24)
        return self.callback_secret


def _public(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if key != "secret"}


def as_object(value: object) -> dict[str, object]:
    """Narrow an untyped app-state payload to a JSON object."""
    return cast("dict[str, object]", value)

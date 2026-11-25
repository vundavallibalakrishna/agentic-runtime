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

    async def list_events(self, *, tenant_id: uuid.UUID | None = None) -> list[dict[str, object]]:
        """Chained rows only. An unhashed in-memory append is not part of the log."""
        from ar_domain.audit.read import chained_only  # noqa: PLC0415

        rows = chained_only(self.events)
        if tenant_id is None:
            return rows
        return [row for row in rows if str(row.get("tenant_id")) == str(tenant_id)]

    async def get(
        self, event_id: int, *, tenant_id: uuid.UUID | None = None
    ) -> dict[str, object] | None:
        for item in await self.list_events(tenant_id=tenant_id):
            if item.get("id") == event_id:
                return item
        return None

    async def verify(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        from_seq: int | None = None,
        to_seq: int | None = None,
    ) -> dict[str, object]:
        from ar_domain.audit.read import verify_public_chain  # noqa: PLC0415

        rows = await self.list_events(tenant_id=tenant_id)
        return verify_public_chain(rows, from_seq=from_seq, to_seq=to_seq)


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
    """The run-callback secret. Outbound webhooks live in WebhookBook, not here."""

    callback_secret: str = ""

    def mint_callback_secret(self) -> str:
        """A new secret that is not installed until the caller commits it."""
        return secrets.token_urlsafe(24)

    def apply_callback_secret(self, secret: str) -> None:
        """Install a secret that has already been committed."""
        self.callback_secret = secret


def as_object(value: object) -> dict[str, object]:
    """Narrow an untyped app-state payload to a JSON object."""
    return cast("dict[str, object]", value)

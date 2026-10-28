"""Seeded identity while the API is on the memory cache.

Playwright and a laptop without Postgres still need users, profile and tenant
settings. The four dev users and an enterprise plan stand in until ``bind_store``
attaches a database (OQ-31).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ar_common.time import utcnow
from ar_contracts.tenants import TenantSettings
from ar_domain.chat.service import demo_id
from ar_domain.identity.models import Plan, Tenant, User
from ar_domain.identity.seed import DEV_USERS, plan_limits
from ar_domain.identity.service import IdentityService, IdentityStore

if TYPE_CHECKING:
    import uuid

    from ar_domain.db.context import TenantContext

_PLAN_ID = demo_id("plan-enterprise")


class MemoryIdentityStore:
    """The identity methods the memory-mode API actually calls."""

    def __init__(self, ctx: TenantContext) -> None:
        self.ctx = ctx
        now = utcnow()
        tenant_id = ctx.tenant_id or demo_id("tenant")
        self.tenant = Tenant(
            id=tenant_id,
            slug="dev",
            name="Dev",
            status="active",
            plan_id=_PLAN_ID,
            isolation_tier="shared",
            data_residency="in",
            billing_currency="INR",
            settings=TenantSettings().model_dump(by_alias=False),
            created_at=now,
        )
        self.plan = Plan(
            id=_PLAN_ID,
            key="enterprise",
            name="Enterprise",
            limits=plan_limits("enterprise"),
            is_public=True,
            created_at=now,
        )
        self.users = {
            demo_id(email.split("@", 1)[0]): User(
                id=demo_id(email.split("@", 1)[0]),
                tenant_id=tenant_id,
                idp_subject=email,
                email=email,
                display_name=display_name,
                status="active",
                created_at=now,
            )
            for email, display_name, _roles in DEV_USERS
        }

    async def get_tenant(self) -> Tenant:
        return self.tenant

    async def get_plan(self, plan_id: uuid.UUID) -> Plan | None:
        return self.plan if plan_id == self.plan.id else None

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        needle = email.lower()
        return next((user for user in self.users.values() if user.email.lower() == needle), None)

    async def list_users(self, *, status: str | None, query: str | None) -> list[User]:
        rows = list(self.users.values())
        if status:
            rows = [row for row in rows if row.status == status]
        if query:
            needle = query.lower()
            rows = [
                row
                for row in rows
                if needle in row.email.lower() or needle in row.display_name.lower()
            ]
        return rows

    async def audit(
        self,
        action: object,
        target_type: str,
        target_id: str | None,
        detail: dict[str, object] | None = None,
    ) -> None:
        del action, target_type, target_id, detail

    async def emit(self, topic: str, payload: dict[str, object]) -> None:
        del topic, payload


def memory_identity(chat: object, ctx: TenantContext) -> IdentityService:
    """One store per process, retargeted to the caller of this request."""
    store = getattr(chat, "_memory_identity", None)
    if not isinstance(store, MemoryIdentityStore):
        store = MemoryIdentityStore(ctx)
        chat._memory_identity = store  # type: ignore[attr-defined]
    store.ctx = ctx
    return IdentityService(cast("IdentityStore", store))


def use_memory_identity(chat: object) -> bool:
    """True after a bind attempt left the process on the memory cache."""
    return (
        bool(getattr(chat, "_bind_attempted", False))
        and getattr(chat, "durable_engine", None) is None
    )

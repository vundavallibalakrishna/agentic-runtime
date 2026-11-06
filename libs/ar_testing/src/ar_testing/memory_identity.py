"""The demo tenant's identity for a store that has no database.

Unit tests and the browser-test harness plug this in as the application's identity
provider. The product reads identity from its database and nowhere else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.identity.models import Plan, Role, RoleAssignment, Tenant, User
from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS
from ar_domain.identity.seed import DEV_USERS, plan_limits
from ar_domain.identity.service import IdentityService, IdentityStore
from ar_domain.identity.tenant_settings import dev_tenant_settings
from ar_testing.demo_people import catalogue

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
            settings=dev_tenant_settings(),
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

    async def grants_for(self, user_id: uuid.UUID) -> list[tuple[RoleAssignment, Role]]:
        """Tenant-scope role grants of a demo person, shaped like database rows."""
        person = next((row for row in catalogue().values() if row.user_id == user_id), None)
        if person is None:
            return []
        return [
            (
                RoleAssignment(
                    tenant_id=self.tenant.id,
                    principal_type="user",
                    principal_id=user_id,
                    scope_type="tenant",
                ),
                Role(key=key, name=key, permissions=sorted(SYSTEM_ROLE_PERMISSIONS[key])),
            )
            for key in person.roles
        ]

    async def user_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        del user_id
        return []

    async def user_team_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        del user_id
        return []

    async def audit_login(self, user: User) -> None:
        del user

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

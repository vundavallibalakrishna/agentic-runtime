"""The demo tenant's identity for a store that has no database.

Unit tests and the browser-test harness plug this in as the application's identity
provider. The product reads identity from its database and nowhere else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.identity.models import Invitation, Plan, Role, RoleAssignment, Tenant, User
from ar_domain.identity.passwords import hash_password
from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS
from ar_domain.identity.recovery_tables import PasswordReset
from ar_domain.identity.seed import DEV_PASSWORD, DEV_USERS, plan_limits
from ar_domain.identity.service import IdentityService, IdentityStore
from ar_domain.identity.tenant_settings import dev_tenant_settings
from ar_testing.demo_people import catalogue

if TYPE_CHECKING:
    import uuid

    from ar_domain.db.context import TenantContext

_PLAN_ID = demo_id("plan-enterprise")
# Argon2 is deliberately slow, so hash the demo password once and share it across the
# in-memory users (they all sign in with the dev password, like the real seed).
_DEV_PASSWORD_HASH = hash_password(DEV_PASSWORD)


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
        self.password_resets: dict[str, PasswordReset] = {}
        self.invitations: dict[str, Invitation] = {}
        self.assignments: list[RoleAssignment] = []
        self.users = {
            demo_id(email.split("@", 1)[0]): User(
                id=demo_id(email.split("@", 1)[0]),
                tenant_id=tenant_id,
                idp_subject=email,
                email=email,
                display_name=display_name,
                status="active",
                password_hash=_DEV_PASSWORD_HASH,
                password_set_at=now,
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

    async def get_user_by_subject(self, subject: str) -> User | None:
        needle = subject.strip()
        return next((user for user in self.users.values() if user.idp_subject == needle), None)

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
            # Someone who joined by invitation: the roles their invitation granted.
            return [
                (row, _role(key))
                for row in self.assignments
                if row.principal_id == user_id
                for key in SYSTEM_ROLE_PERMISSIONS
                if row.role_id == _role(key).id
            ]
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

    def add(self, row: object) -> None:
        """Keep a new row: a reset, an invitation, an invited person or their role."""
        if isinstance(row, PasswordReset):
            self.password_resets[row.token_hash] = row
        elif isinstance(row, Invitation):
            if row.id is None:
                row.id = new_id()
            self.invitations[row.token_hash] = row
        elif isinstance(row, User) and row.kind != "service":
            # The memory store keeps no service accounts, so it keeps no user for one.
            self.users[row.id] = row
        elif isinstance(row, RoleAssignment):
            self.assignments.append(row)

    async def invitation_by_hash(self, token_hash: str) -> Invitation | None:
        return self.invitations.get(token_hash)

    async def list_invitations(self) -> list[Invitation]:
        return list(self.invitations.values())

    async def get_invitation(self, invitation_id: uuid.UUID) -> Invitation | None:
        return next((row for row in self.invitations.values() if row.id == invitation_id), None)

    async def list_api_keys(
        self, *, user_id: uuid.UUID | None, service_account_id: uuid.UUID | None
    ) -> list[object]:
        """The memory store keeps no personal keys."""
        del user_id, service_account_id
        return []

    async def list_roles(self) -> list[Role]:
        return [_role(key) for key in sorted(SYSTEM_ROLE_PERMISSIONS)]

    async def get_role_by_key(self, key: str) -> Role | None:
        return _role(key) if key in SYSTEM_ROLE_PERMISSIONS else None

    async def password_reset_by_hash(self, token_hash: str) -> PasswordReset | None:
        return self.password_resets.get(token_hash)

    async def audit_password_reset(self, user: User) -> None:
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


def _role(key: str) -> Role:
    """A system role as the memory store hands it out: one fixed id for each key."""
    return Role(
        id=demo_id(f"role-{key}"),
        key=key,
        name=key,
        permissions=sorted(SYSTEM_ROLE_PERMISSIONS[key]),
    )


class _Statuses(dict[object, str]):
    """People's status as the product store reads it, answered from the identity rows.

    A database-backed store reloads this from the ``users`` table on every request. With
    no database the rows live in ``MemoryIdentityStore``, so the lookup goes there.
    """

    def __init__(self, known: dict[object, str], users: dict[uuid.UUID, User]) -> None:
        super().__init__(known)
        self._users = users

    def get(self, key: Any, default: Any = None) -> Any:
        user = self._users.get(key)
        return user.status if user is not None else super().get(key, default)


def memory_identity(chat: object, ctx: TenantContext) -> IdentityService:
    """One store per process, retargeted to the caller of this request."""
    store = getattr(chat, "_memory_identity", None)
    if not isinstance(store, MemoryIdentityStore):
        store = MemoryIdentityStore(ctx)
        chat._memory_identity = store  # type: ignore[attr-defined]
        known = getattr(chat, "user_statuses", None)
        if isinstance(known, dict):
            chat.user_statuses = _Statuses(known, store.users)  # type: ignore[attr-defined]
    store.ctx = ctx
    return IdentityService(cast("IdentityStore", store))

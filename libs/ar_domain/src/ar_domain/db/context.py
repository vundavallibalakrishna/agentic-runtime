"""Request tenancy context. Spec: docs/04-data/rls.md §2."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime  # noqa: TC003
from typing import Literal

PrincipalKind = Literal["user", "service_account", "platform_admin", "system", "agent", "guest"]
AuthMethod = Literal["session", "bearer", "api_key", "scim", "system", "none"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated caller. Permissions are the effective tenant-wide set."""

    kind: PrincipalKind
    id: str
    tenant_id: uuid.UUID | None
    permissions: frozenset[str] = field(default_factory=frozenset)
    team_permissions: frozenset[tuple[uuid.UUID, str]] = field(default_factory=frozenset)
    scopes: frozenset[str] = field(default_factory=frozenset)
    auth_method: AuthMethod = "none"
    email: str | None = None
    display_name: str | None = None
    session_id: str | None = None
    csrf_token: str | None = None
    step_up_at: datetime | None = None
    tenant_status: str = "active"
    user_status: str = "active"
    support_grant_id: uuid.UUID | None = None
    support_level: str | None = None
    api_key_id: uuid.UUID | None = None
    roles: frozenset[str] = field(default_factory=frozenset)

    def can_read_content(self) -> bool:
        """Metadata support grants and unscoped platform admins cannot read content."""
        if self.kind == "platform_admin":
            return self.support_level == "content"
        return self.support_level != "metadata"

    def allows(self, permission: str, *, team_id: uuid.UUID | None = None) -> bool:
        """Return whether this principal holds ``permission``.

        API-key scopes, when non-empty, intersect the principal's permissions.
        Team-scoped grants apply only when ``team_id`` is the scoped team.
        """
        granted = permission in self.permissions
        if team_id is not None and (team_id, permission) in self.team_permissions:
            granted = True
        if not granted:
            return False
        return not (self.scopes and permission not in self.scopes)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Tenant, actor and request id bound to one transaction."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    principal: Principal
    request_id: str

    @classmethod
    def from_principal(cls, principal: Principal, request_id: str) -> TenantContext:
        """Build a context. Platform calls without a tenant cannot use this."""
        if principal.tenant_id is None:
            raise ValueError("tenant context requires a tenant")
        user_id: uuid.UUID | None = None
        if principal.kind == "user":
            user_id = uuid.UUID(principal.id)
        return cls(
            tenant_id=principal.tenant_id,
            user_id=user_id,
            principal=principal,
            request_id=request_id,
        )

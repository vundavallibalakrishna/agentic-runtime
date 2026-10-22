"""Identity business rules. Spec: docs/03-specs/02-identity-tenancy.md."""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from ar_common.errors import (
    ArError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits, TenantSettings, UserSettings
from ar_domain.audit.actions import AuditAction
from ar_domain.identity.limits import merge_settings, snakeize, validate_tenant_settings
from ar_domain.identity.models import (
    ApiKey,
    Group,
    GroupMember,
    IdentityProvider,
    Invitation,
    Plan,
    Role,
    RoleAssignment,
    ScimToken,
    ServiceAccount,
    SupportAccessGrant,
    Team,
    TeamMember,
    Tenant,
    TenantDomain,
    User,
)
from ar_domain.identity.permissions import PERMISSION_KEYS, SYSTEM_ROLE_NAMES
from ar_domain.identity.resolver import RoleGrant, resolve_access
from ar_domain.identity.scim_ops import apply_user_patch, member_ids_from_patch, parse_eq_filter
from ar_domain.identity.tokens import new_api_key, new_invitation_token, new_scim_token

if TYPE_CHECKING:
    from ar_domain.db.context import TenantContext


class IdentityStore(Protocol):
    """Persistence used by :class:`IdentityService`. Implemented by the repository."""

    ctx: TenantContext

    async def get_tenant(self) -> Tenant | None: ...
    async def get_plan(self, plan_id: uuid.UUID) -> Plan | None: ...
    async def get_user(self, user_id: uuid.UUID) -> User | None: ...
    async def get_user_by_email(self, email: str) -> User | None: ...
    async def list_users(self, *, status: str | None, query: str | None) -> list[User]: ...
    async def list_groups(self, *, source: str | None) -> list[Group]: ...
    async def get_group(self, group_id: uuid.UUID) -> Group | None: ...
    async def group_member_ids(self, group_id: uuid.UUID) -> list[uuid.UUID]: ...
    async def user_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]: ...
    async def list_teams(self) -> list[Team]: ...
    async def get_team(self, team_id: uuid.UUID) -> Team | None: ...
    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]: ...
    async def user_team_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]: ...
    async def is_team_lead(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...
    async def list_roles(self) -> list[Role]: ...
    async def get_role(self, role_id: uuid.UUID) -> Role | None: ...
    async def get_role_by_key(self, key: str) -> Role | None: ...
    async def list_assignments(self) -> list[RoleAssignment]: ...
    async def grants_for(self, user_id: uuid.UUID) -> list[tuple[RoleAssignment, Role]]: ...
    async def count_other_admins(self, excluding: uuid.UUID | None) -> int: ...
    async def get_assignment(self, assignment_id: uuid.UUID) -> RoleAssignment | None: ...
    async def list_api_keys(
        self, *, user_id: uuid.UUID | None, service_account_id: uuid.UUID | None
    ) -> list[ApiKey]: ...
    async def get_api_key(self, api_key_id: uuid.UUID) -> ApiKey | None: ...
    async def list_service_accounts(self) -> list[ServiceAccount]: ...
    async def get_service_account(self, service_account_id: uuid.UUID) -> ServiceAccount | None: ...
    async def list_invitations(self) -> list[Invitation]: ...
    async def get_invitation(self, invitation_id: uuid.UUID) -> Invitation | None: ...
    async def invitation_by_hash(self, token_hash: str) -> Invitation | None: ...
    async def list_domains(self) -> list[TenantDomain]: ...
    async def get_domain(self, domain_id: uuid.UUID) -> TenantDomain | None: ...
    async def list_idps(self) -> list[IdentityProvider]: ...
    async def get_idp(self, idp_id: uuid.UUID) -> IdentityProvider | None: ...
    async def list_scim_tokens(self) -> list[ScimToken]: ...
    async def list_support_grants(self) -> list[SupportAccessGrant]: ...
    async def active_support_grant(
        self, operator_subject: str, now: datetime
    ) -> SupportAccessGrant | None: ...
    def add(self, row: object) -> None: ...
    async def delete(self, row: object) -> None: ...
    async def audit(
        self,
        action: AuditAction,
        target_type: str,
        target_id: str | None,
        detail: dict[str, object] | None = None,
    ) -> None: ...
    async def emit(self, topic: str, payload: dict[str, object]) -> None: ...


class IdentityService:
    """Tenant identity operations. The store is the repository or a test double."""

    def __init__(self, store: IdentityStore) -> None:
        self.store = store

    @property
    def ctx(self) -> TenantContext:
        return self.store.ctx

    async def effective_for(self, user_id: uuid.UUID) -> tuple[frozenset[str], frozenset[str]]:
        pairs = await self.store.grants_for(user_id)
        grants = [
            RoleGrant(
                principal_type=assignment.principal_type,
                principal_id=assignment.principal_id,
                role_key=role.key,
                permissions=tuple(role.permissions),
                scope_type=assignment.scope_type,
                scope_id=assignment.scope_id,
            )
            for assignment, role in pairs
        ]
        groups = set(await self.store.user_group_ids(user_id))
        teams = set(await self.store.user_team_ids(user_id))
        access = resolve_access(user_id, group_ids=groups, team_ids=teams, grants=grants)
        return access.permissions, access.roles

    async def update_tenant(
        self, *, name: str | None, settings_patch: dict[str, object] | None
    ) -> Tenant:
        tenant = await self._tenant()
        plan = await self.store.get_plan(tenant.plan_id)
        if plan is None:
            raise NotFoundError("plan not found")
        if name:
            tenant.name = name
        if settings_patch:
            current = TenantSettings.model_validate(tenant.settings)
            merged = merge_settings(current, settings_patch)
            limits = PlanLimits.model_validate(plan.limits)
            tenant.settings = validate_tenant_settings(merged, limits).model_dump(by_alias=False)
        await self.store.audit(
            AuditAction.TENANT_UPDATED, "tenant", str(tenant.id), {"name": tenant.name}
        )
        await self.store.emit("tenant.created", {"tenant_id": str(tenant.id), "updated": True})
        return tenant

    async def update_me(
        self, *, display_name: str | None, settings: dict[str, object] | None
    ) -> User:
        user = await self._self()
        if display_name:
            user.display_name = display_name
        if settings:
            current = UserSettings.model_validate(user.settings or {})
            user.settings = merge_user(current, settings).model_dump(by_alias=False)
        return user

    async def patch_user(
        self, user_id: uuid.UUID, *, status: str | None, attributes: dict[str, object] | None
    ) -> User:
        user = await self._user(user_id)
        if status is not None:
            if status not in {"active", "suspended"}:
                raise ValidationFailedError("status must be active or suspended")
            user.status = status
            if status == "suspended":
                await self._revoke_user_keys(user_id)
                await self.store.audit(AuditAction.USER_SUSPENDED, "user", str(user_id), {})
                await self.store.emit("user.deprovisioned", {"user_id": str(user_id)})
                from ar_domain.routines.engine import pause_for_owner  # noqa: PLC0415

                pause_for_owner(self.store, user.tenant_id, user_id)
        if attributes is not None:
            user.attributes = {**user.attributes, **attributes}
        return user

    async def invite(self, emails: list[str], role_keys: list[str]) -> list[tuple[Invitation, str]]:
        if len(emails) > 100:
            raise ValidationFailedError("at most 100 invitations")
        for key in role_keys:
            if key not in SYSTEM_ROLE_NAMES and key not in PERMISSION_KEYS:
                role = await self.store.get_role_by_key(key)
                if role is None:
                    raise ValidationFailedError(f"unknown role {key}")
        created: list[tuple[Invitation, str]] = []
        for email in emails:
            raw, digest = new_invitation_token()
            row = Invitation(
                tenant_id=self.ctx.tenant_id,
                email=email,
                role_keys=role_keys or ["member"],
                token_hash=digest,
                invited_by=self.ctx.user_id,
                expires_at=utcnow() + timedelta(days=7),
            )
            self.store.add(row)
            created.append((row, raw))
            await self.store.emit(
                "invitation.created",
                {"email": email, "role_keys": role_keys or ["member"]},
            )
        return created

    async def revoke_invitation(self, invitation_id: uuid.UUID) -> None:
        row = await self.store.get_invitation(invitation_id)
        if row is None:
            raise NotFoundError("invitation not found")
        row.revoked_at = utcnow()

    async def accept_invitation(self, token_hash: str, email: str) -> Invitation:
        row = await self.store.invitation_by_hash(token_hash)
        if row is None or row.revoked_at is not None or row.accepted_at is not None:
            raise NotFoundError("invitation not found")
        if row.expires_at < utcnow():
            raise ArError(ErrorCode.INVALID_STATE, "invitation expired")
        if row.email.lower() != email.lower():
            raise ForbiddenError("invitation email does not match")
        row.accepted_at = utcnow()
        return row

    async def create_group(self, name: str) -> Group:
        row = Group(tenant_id=self.ctx.tenant_id, name=name, source="local")
        self.store.add(row)
        await self.store.emit("membership.changed", {"group": name, "op": "create"})
        return row

    async def delete_group(self, group_id: uuid.UUID) -> None:
        group = await self._group(group_id)
        if group.source != "local":
            raise ArError(ErrorCode.INVALID_STATE, "only local groups can be deleted")
        await self.store.delete(group)

    async def add_group_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        group = await self._group(group_id)
        if group.source != "local":
            raise ArError(ErrorCode.INVALID_STATE, "membership is managed upstream")
        await self._user(user_id)
        self.store.add(
            GroupMember(tenant_id=self.ctx.tenant_id, group_id=group_id, user_id=user_id)
        )
        await self.store.emit(
            "membership.changed", {"group_id": str(group_id), "user_id": str(user_id)}
        )

    async def remove_group_member(self, group_id: uuid.UUID, user_id: uuid.UUID) -> None:
        group = await self._group(group_id)
        if group.source != "local":
            raise ArError(ErrorCode.INVALID_STATE, "membership is managed upstream")
        for member_id in await self.store.group_member_ids(group_id):
            if member_id == user_id:
                await self.store.delete(
                    GroupMember(tenant_id=self.ctx.tenant_id, group_id=group_id, user_id=user_id)
                )
                return
        raise NotFoundError("member not found")

    async def create_team(self, *, slug: str, name: str, description: str) -> Team:
        row = Team(tenant_id=self.ctx.tenant_id, slug=slug, name=name, description=description)
        self.store.add(row)
        return row

    async def delete_team(self, team_id: uuid.UUID) -> None:
        team = await self._team(team_id)
        await self.store.delete(team)

    async def add_team_member(self, team_id: uuid.UUID, user_id: uuid.UUID, team_role: str) -> None:
        await self._assert_team_manager(team_id)
        if team_role not in {"member", "lead"}:
            raise ValidationFailedError("team_role must be member or lead")
        await self._user(user_id)
        self.store.add(
            TeamMember(
                tenant_id=self.ctx.tenant_id,
                team_id=team_id,
                user_id=user_id,
                team_role=team_role,
            )
        )

    async def create_role(
        self, *, key: str, name: str, description: str, permissions: list[str]
    ) -> Role:
        unknown = [item for item in permissions if item not in PERMISSION_KEYS]
        if unknown or key.startswith("platform"):
            raise ValidationFailedError("unknown permission")
        row = Role(
            tenant_id=self.ctx.tenant_id,
            key=key,
            name=name,
            description=description,
            permissions=permissions,
            is_system=False,
        )
        self.store.add(row)
        await self.store.emit("role.changed", {"key": key})
        return row

    async def update_role(
        self, role_id: uuid.UUID, *, name: str | None, permissions: list[str] | None
    ) -> Role:
        role = await self._role(role_id)
        if role.is_system or role.tenant_id is None:
            raise ArError(ErrorCode.INVALID_STATE, "system roles are immutable")
        if name:
            role.name = name
        if permissions is not None:
            role.permissions = permissions
        await self.store.emit("role.changed", {"key": role.key})
        return role

    async def delete_role(self, role_id: uuid.UUID) -> None:
        role = await self._role(role_id)
        if role.is_system or role.tenant_id is None:
            raise ArError(ErrorCode.INVALID_STATE, "system roles are immutable")
        await self.store.delete(role)

    async def assign_role(
        self,
        *,
        role_id: uuid.UUID,
        principal_type: str,
        principal_id: uuid.UUID,
        scope_type: str,
        scope_id: uuid.UUID | None,
    ) -> RoleAssignment:
        role = await self._role(role_id)
        if scope_type == "team" and scope_id is None:
            raise ValidationFailedError("team scope requires scope_id")
        row = RoleAssignment(
            tenant_id=self.ctx.tenant_id,
            role_id=role.id,
            principal_type=principal_type,
            principal_id=principal_id,
            scope_type=scope_type,
            scope_id=scope_id,
            created_by=self.ctx.user_id,
        )
        self.store.add(row)
        await self.store.emit("role.changed", {"role": role.key, "principal_id": str(principal_id)})
        return row

    async def delete_assignment(self, assignment_id: uuid.UUID) -> None:
        row = await self.store.get_assignment(assignment_id)
        if row is None:
            raise NotFoundError("assignment not found")
        role = await self.store.get_role(row.role_id)
        if role is not None and role.key == "tenant_admin" and row.principal_type == "user":
            remaining = await self.store.count_other_admins(row.id)
            if remaining < 1:
                raise ConflictError("the tenant needs at least one tenant admin")
        await self.store.delete(row)

    async def create_service_account(
        self, *, name: str, description: str, allow_on_behalf_of: bool
    ) -> ServiceAccount:
        row = ServiceAccount(
            tenant_id=self.ctx.tenant_id,
            name=name,
            description=description,
            allow_on_behalf_of=allow_on_behalf_of,
            created_by=self.ctx.user_id,
        )
        self.store.add(row)
        if allow_on_behalf_of:
            await self.store.audit(
                AuditAction.SERVICE_ACCOUNT_ON_BEHALF_OF_ENABLED,
                "service_account",
                str(row.id),
                {},
            )
        return row

    async def create_api_key(
        self,
        *,
        name: str,
        scopes: list[str],
        expires_in_days: int,
        service_account_id: uuid.UUID | None,
    ) -> tuple[ApiKey, str]:
        if not 1 <= expires_in_days <= 365:
            raise ValidationFailedError("expires_in_days must be between 1 and 365")
        full, prefix, digest = new_api_key()
        user_id = None if service_account_id else self.ctx.user_id
        row = ApiKey(
            tenant_id=self.ctx.tenant_id,
            name=name,
            prefix=prefix,
            secret_hash=digest,
            scopes=scopes,
            service_account_id=service_account_id,
            user_id=user_id,
            expires_at=utcnow() + timedelta(days=expires_in_days),
            created_by=self.ctx.user_id,
        )
        self.store.add(row)
        await self.store.audit(AuditAction.API_KEY_CREATED, "api_key", str(row.id), {"name": name})
        return row, full

    async def revoke_api_key(self, api_key_id: uuid.UUID) -> None:
        row = await self.store.get_api_key(api_key_id)
        if row is None:
            raise NotFoundError("api key not found")
        if (
            row.user_id is not None
            and row.user_id != self.ctx.user_id
            and not self.ctx.principal.allows("service_accounts:manage")
        ):
            raise ForbiddenError("cannot revoke another user's key")
        row.revoked_at = utcnow()
        await self.store.audit(AuditAction.API_KEY_REVOKED, "api_key", str(row.id), {})

    async def create_scim_token(self) -> tuple[ScimToken, str]:
        full, prefix, digest = new_scim_token()
        row = ScimToken(
            tenant_id=self.ctx.tenant_id,
            prefix=prefix,
            secret_hash=digest,
            created_by=self.ctx.user_id,
        )
        self.store.add(row)
        return row, full

    async def add_domain(self, domain: str, token: str) -> TenantDomain:
        row = TenantDomain(tenant_id=self.ctx.tenant_id, domain=domain, verification_token=token)
        self.store.add(row)
        return row

    async def verify_domain(self, domain_id: uuid.UUID, txt_values: list[str]) -> TenantDomain:
        row = await self.store.get_domain(domain_id)
        if row is None:
            raise NotFoundError("domain not found")
        if row.verification_token not in txt_values:
            raise ValidationFailedError("domain verification failed")
        row.verified_at = utcnow()
        return row

    async def scim_set_active(
        self, user_id: uuid.UUID, operations: list[dict[str, object]]
    ) -> User:
        user = await self._user(user_id)
        active = apply_user_patch(active=user.status == "active", operations=operations)
        user.status = "active" if active else "deprovisioned"
        if not active:
            await self._revoke_user_keys(user_id)
            await self.store.audit(AuditAction.SCIM_USER_DEPROVISIONED, "user", str(user_id), {})
        return user

    async def scim_patch_group(
        self, group_id: uuid.UUID, operations: list[dict[str, object]]
    ) -> Group:
        group = await self._group(group_id)
        added, removed = member_ids_from_patch(operations)
        for identifier in added:
            self.store.add(
                GroupMember(
                    tenant_id=self.ctx.tenant_id, group_id=group_id, user_id=uuid.UUID(identifier)
                )
            )
        for identifier in removed:
            await self.store.delete(
                GroupMember(
                    tenant_id=self.ctx.tenant_id,
                    group_id=group_id,
                    user_id=uuid.UUID(identifier),
                )
            )
        return group

    def parse_filter(self, expression: str | None) -> tuple[str, str] | None:
        return parse_eq_filter(expression)

    async def grant_support(
        self, *, operator_subject: str, operator_email: str, level: str, reason: str, hours: int
    ) -> SupportAccessGrant:
        if level not in {"metadata", "content"}:
            raise ValidationFailedError("level must be metadata or content")
        if self.ctx.user_id is None:
            raise ForbiddenError("a user must grant support access")
        row = SupportAccessGrant(
            tenant_id=self.ctx.tenant_id,
            operator_subject=operator_subject,
            operator_email=operator_email,
            level=level,
            reason=reason,
            granted_by=self.ctx.user_id,
            expires_at=utcnow() + timedelta(hours=hours),
        )
        self.store.add(row)
        await self.store.audit(
            AuditAction.SUPPORT_ACCESS_GRANTED,
            "support_access_grant",
            str(row.id),
            {"level": level},
        )
        return row

    async def _revoke_user_keys(self, user_id: uuid.UUID) -> None:
        keys = await self.store.list_api_keys(user_id=user_id, service_account_id=None)
        now = utcnow()
        for key in keys:
            key.revoked_at = now

    async def _assert_team_manager(self, team_id: uuid.UUID) -> None:
        if self.ctx.principal.allows("teams:manage"):
            return
        if self.ctx.user_id is not None and await self.store.is_team_lead(
            team_id, self.ctx.user_id
        ):
            return
        raise ForbiddenError("team lead or teams:manage is required")

    async def _tenant(self) -> Tenant:
        tenant = await self.store.get_tenant()
        if tenant is None:
            raise NotFoundError("tenant not found")
        return tenant

    async def current_user(self) -> User:
        """Return the caller. Profile routes serialize this as ``Me``."""
        return await self._self()

    async def _self(self) -> User:
        if self.ctx.user_id is None:
            raise ForbiddenError("only users can update their profile")
        return await self._user(self.ctx.user_id)

    async def _user(self, user_id: uuid.UUID) -> User:
        user = await self.store.get_user(user_id)
        if user is None:
            raise NotFoundError("user not found")
        return user

    async def _group(self, group_id: uuid.UUID) -> Group:
        group = await self.store.get_group(group_id)
        if group is None:
            raise NotFoundError("group not found")
        return group

    async def _team(self, team_id: uuid.UUID) -> Team:
        team = await self.store.get_team(team_id)
        if team is None:
            raise NotFoundError("team not found")
        return team

    async def _role(self, role_id: uuid.UUID) -> Role:
        role = await self.store.get_role(role_id)
        if role is None:
            raise NotFoundError("role not found")
        return role


def merge_user(current: UserSettings, patch: dict[str, object]) -> UserSettings:
    """Merge a partial user settings document."""
    merged = current.model_dump(by_alias=False)
    for key, value in snakeize(patch).items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return UserSettings.model_validate(merged)


def assert_step_up(
    principal_step_up_at: object, *, now: object, ttl_s: int, required: bool
) -> None:
    """Reject session callers whose step-up is missing or older than ``ttl_s``."""
    if not required:
        return
    if principal_step_up_at is None:
        raise ForbiddenError("step-up authentication is required")
    from datetime import datetime  # noqa: PLC0415

    if not isinstance(principal_step_up_at, datetime) or not isinstance(now, datetime):
        raise ForbiddenError("step-up authentication is required")
    if (now - principal_step_up_at).total_seconds() > ttl_s:
        raise ForbiddenError("step-up authentication expired")

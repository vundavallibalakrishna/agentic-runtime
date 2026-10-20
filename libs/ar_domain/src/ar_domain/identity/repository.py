"""Identity queries. Spec: docs/04-data/schema.md §1."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from ar_domain.audit.service import record_for_context
from ar_domain.db import BaseRepository
from ar_domain.events.service import emit
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

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.audit.actions import AuditAction
    from ar_domain.db.context import TenantContext


class IdentityRepository(BaseRepository):
    """Tenant-scoped identity queries. Audit and outbox share the caller's transaction."""

    def __init__(self, session: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(session, ctx)

    async def get_tenant(self) -> Tenant | None:
        return await self.session.get(Tenant, self.ctx.tenant_id)

    async def get_plan(self, plan_id: uuid.UUID) -> Plan | None:
        return await self.session.get(Plan, plan_id)

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return await self.session.scalar(
            select(User).where(User.tenant_id == self.ctx.tenant_id, User.id == user_id)
        )

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.tenant_id == self.ctx.tenant_id, User.email == email)
        )

    async def list_users(self, *, status: str | None, query: str | None) -> list[User]:
        stmt = select(User).where(User.tenant_id == self.ctx.tenant_id)
        if status:
            stmt = stmt.where(User.status == status)
        if query:
            stmt = stmt.where(User.email.ilike(f"%{query}%"))
        return list((await self.session.scalars(stmt.order_by(User.email))).all())

    async def list_groups(self, *, source: str | None) -> list[Group]:
        stmt = select(Group).where(Group.tenant_id == self.ctx.tenant_id)
        if source:
            stmt = stmt.where(Group.source == source)
        return list((await self.session.scalars(stmt.order_by(Group.name))).all())

    async def get_group(self, group_id: uuid.UUID) -> Group | None:
        return await self.session.scalar(
            select(Group).where(Group.tenant_id == self.ctx.tenant_id, Group.id == group_id)
        )

    async def group_member_ids(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        rows = await self.session.scalars(
            select(GroupMember.user_id).where(
                GroupMember.tenant_id == self.ctx.tenant_id, GroupMember.group_id == group_id
            )
        )
        return list(rows.all())

    async def user_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        rows = await self.session.scalars(
            select(GroupMember.group_id).where(
                GroupMember.tenant_id == self.ctx.tenant_id, GroupMember.user_id == user_id
            )
        )
        return list(rows.all())

    async def list_teams(self) -> list[Team]:
        rows = await self.session.scalars(
            select(Team).where(Team.tenant_id == self.ctx.tenant_id).order_by(Team.slug)
        )
        return list(rows.all())

    async def get_team(self, team_id: uuid.UUID) -> Team | None:
        return await self.session.scalar(
            select(Team).where(Team.tenant_id == self.ctx.tenant_id, Team.id == team_id)
        )

    async def team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        rows = await self.session.scalars(
            select(TeamMember).where(
                TeamMember.tenant_id == self.ctx.tenant_id, TeamMember.team_id == team_id
            )
        )
        return list(rows.all())

    async def user_team_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        rows = await self.session.scalars(
            select(TeamMember.team_id).where(
                TeamMember.tenant_id == self.ctx.tenant_id, TeamMember.user_id == user_id
            )
        )
        return list(rows.all())

    async def is_team_lead(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        row = await self.session.scalar(
            select(TeamMember).where(
                TeamMember.tenant_id == self.ctx.tenant_id,
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
                TeamMember.team_role == "lead",
            )
        )
        return row is not None

    async def list_roles(self) -> list[Role]:
        rows = await self.session.scalars(select(Role).order_by(Role.key))
        return list(rows.all())

    async def get_role(self, role_id: uuid.UUID) -> Role | None:
        return await self.session.get(Role, role_id)

    async def get_role_by_key(self, key: str) -> Role | None:
        return await self.session.scalar(
            select(Role).where(Role.key == key, Role.tenant_id.is_(None))
        )

    async def list_assignments(self) -> list[RoleAssignment]:
        rows = await self.session.scalars(
            select(RoleAssignment).where(RoleAssignment.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def grants_for(self, user_id: uuid.UUID) -> list[tuple[RoleAssignment, Role]]:
        rows = await self.session.execute(
            select(RoleAssignment, Role)
            .join(Role, Role.id == RoleAssignment.role_id)
            .where(RoleAssignment.tenant_id == self.ctx.tenant_id)
        )
        matched: list[tuple[RoleAssignment, Role]] = []
        groups = set(await self.user_group_ids(user_id))
        teams = set(await self.user_team_ids(user_id))
        for assignment, role in rows.all():
            if (
                (assignment.principal_type == "user" and assignment.principal_id == user_id)
                or (assignment.principal_type == "group" and assignment.principal_id in groups)
                or (assignment.principal_type == "team" and assignment.principal_id in teams)
            ):
                matched.append((assignment, role))
        return matched

    async def count_other_admins(self, excluding: uuid.UUID | None) -> int:
        admin = await self.get_role_by_key("tenant_admin")
        if admin is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(RoleAssignment)
            .where(
                RoleAssignment.tenant_id == self.ctx.tenant_id,
                RoleAssignment.role_id == admin.id,
                RoleAssignment.principal_type == "user",
                RoleAssignment.scope_type == "tenant",
            )
        )
        if excluding is not None:
            stmt = stmt.where(RoleAssignment.id != excluding)
        value = await self.session.scalar(stmt)
        return int(value or 0)

    async def get_assignment(self, assignment_id: uuid.UUID) -> RoleAssignment | None:
        return await self.session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.tenant_id == self.ctx.tenant_id, RoleAssignment.id == assignment_id
            )
        )

    async def list_api_keys(
        self, *, user_id: uuid.UUID | None, service_account_id: uuid.UUID | None
    ) -> list[ApiKey]:
        stmt = select(ApiKey).where(
            ApiKey.tenant_id == self.ctx.tenant_id, ApiKey.revoked_at.is_(None)
        )
        if user_id is not None:
            stmt = stmt.where(ApiKey.user_id == user_id)
        if service_account_id is not None:
            stmt = stmt.where(ApiKey.service_account_id == service_account_id)
        return list((await self.session.scalars(stmt)).all())

    async def get_api_key_by_prefix(self, prefix: str) -> ApiKey | None:
        return await self.session.scalar(select(ApiKey).where(ApiKey.prefix == prefix))

    async def get_api_key(self, api_key_id: uuid.UUID) -> ApiKey | None:
        return await self.session.scalar(
            select(ApiKey).where(ApiKey.tenant_id == self.ctx.tenant_id, ApiKey.id == api_key_id)
        )

    async def list_service_accounts(self) -> list[ServiceAccount]:
        rows = await self.session.scalars(
            select(ServiceAccount).where(ServiceAccount.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def get_service_account(self, service_account_id: uuid.UUID) -> ServiceAccount | None:
        return await self.session.scalar(
            select(ServiceAccount).where(
                ServiceAccount.tenant_id == self.ctx.tenant_id,
                ServiceAccount.id == service_account_id,
            )
        )

    async def list_invitations(self) -> list[Invitation]:
        rows = await self.session.scalars(
            select(Invitation).where(Invitation.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def get_invitation(self, invitation_id: uuid.UUID) -> Invitation | None:
        return await self.session.scalar(
            select(Invitation).where(
                Invitation.tenant_id == self.ctx.tenant_id, Invitation.id == invitation_id
            )
        )

    async def invitation_by_hash(self, token_hash: str) -> Invitation | None:
        return await self.session.scalar(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )

    async def list_domains(self) -> list[TenantDomain]:
        rows = await self.session.scalars(
            select(TenantDomain).where(TenantDomain.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def get_domain(self, domain_id: uuid.UUID) -> TenantDomain | None:
        return await self.session.scalar(
            select(TenantDomain).where(
                TenantDomain.tenant_id == self.ctx.tenant_id, TenantDomain.id == domain_id
            )
        )

    async def list_idps(self) -> list[IdentityProvider]:
        rows = await self.session.scalars(
            select(IdentityProvider).where(IdentityProvider.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def get_idp(self, idp_id: uuid.UUID) -> IdentityProvider | None:
        return await self.session.scalar(
            select(IdentityProvider).where(
                IdentityProvider.tenant_id == self.ctx.tenant_id, IdentityProvider.id == idp_id
            )
        )

    async def list_scim_tokens(self) -> list[ScimToken]:
        rows = await self.session.scalars(
            select(ScimToken).where(ScimToken.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def get_scim_token_by_prefix(self, prefix: str) -> ScimToken | None:
        return await self.session.scalar(select(ScimToken).where(ScimToken.prefix == prefix))

    async def list_support_grants(self) -> list[SupportAccessGrant]:
        rows = await self.session.scalars(
            select(SupportAccessGrant).where(SupportAccessGrant.tenant_id == self.ctx.tenant_id)
        )
        return list(rows.all())

    async def active_support_grant(
        self, operator_subject: str, now: datetime
    ) -> SupportAccessGrant | None:
        return await self.session.scalar(
            select(SupportAccessGrant).where(
                SupportAccessGrant.tenant_id == self.ctx.tenant_id,
                SupportAccessGrant.operator_subject == operator_subject,
                SupportAccessGrant.revoked_at.is_(None),
                SupportAccessGrant.expires_at > now,
            )
        )

    def add(self, row: object) -> None:
        self.session.add(row)

    async def delete(self, row: object) -> None:
        await self.session.delete(row)

    async def audit(
        self,
        action: AuditAction,
        target_type: str,
        target_id: str | None,
        detail: dict[str, object] | None = None,
    ) -> None:
        await record_for_context(
            self.session,
            self.ctx,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )

    async def emit(self, topic: str, payload: dict[str, object]) -> None:
        await emit(self.session, self.ctx, topic, payload)

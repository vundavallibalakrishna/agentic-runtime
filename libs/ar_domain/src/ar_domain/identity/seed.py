"""Idempotent seed for plans, system roles and the dev tenant.

Spec: docs/06-security/authn-authz.md §4, docs/03-specs/02-identity-tenancy.md §3.10.
Lives next to the identity models so the seed can insert rows without a
cross-package model import.
"""

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import select

from ar_common.ids import new_id
from ar_contracts.tenants import PlanLimits, TenantSettings
from ar_domain.demo_ids import demo_id
from ar_domain.identity.models import Plan, Role, RoleAssignment, Team, TeamMember, Tenant, User
from ar_domain.identity.permissions import SYSTEM_ROLE_NAMES, SYSTEM_ROLE_PERMISSIONS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
DEV_USERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("admin@dev.local", "Dev Admin", ("tenant_admin",)),
    ("builder@dev.local", "Dev Builder", ("builder", "tool_owner", "knowledge_manager")),
    ("member@dev.local", "Dev Member", ("member",)),
    ("approver@dev.local", "Dev Approver", ("approver",)),
)


def plan_limits(key: str) -> dict[str, object]:
    """Plan documents. Enterprise and self-hosted match the spec defaults."""
    base = PlanLimits().model_dump(by_alias=False)
    if key == "free":
        base["max_users"] = 5
        base["max_agents"] = 3
        base["api_rpm"] = 60
        features = dict(base["features"])
        features["teams_channel"] = False
        features["email_channel"] = False
        base["features"] = features
    elif key == "team":
        base["max_users"] = 50
        base["api_rpm"] = 600
    elif key == "self_hosted":
        base["max_users"] = None
        base["api_rpm"] = 6000
    return base


async def user_id_for_email(session: AsyncSession, tenant_id: uuid.UUID, email: str) -> uuid.UUID:
    """Return the seeded user id, or raise when the email is missing."""
    user = await session.scalar(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    )
    if user is None:
        raise RuntimeError("dev admin was not seeded")
    return user.id


async def ensure_everyone_team(
    session: AsyncSession, tenant_id: uuid.UUID, admin_id: uuid.UUID
) -> None:
    """Create the default team and make the admin its lead. Safe to run twice."""
    team = await session.scalar(
        select(Team).where(Team.tenant_id == tenant_id, Team.slug == "everyone")
    )
    if team is not None:
        return
    team = Team(id=new_id(), tenant_id=tenant_id, slug="everyone", name="Everyone")
    session.add(team)
    await session.flush()
    session.add(
        TeamMember(tenant_id=tenant_id, team_id=team.id, user_id=admin_id, team_role="lead")
    )


async def apply(session: AsyncSession) -> uuid.UUID:
    """Insert catalogue rows and the dev tenant. Safe to run twice."""
    plans = await _plans(session)
    roles = await _roles(session)
    tenant = await _tenant(session, plans["enterprise"].id)
    await _users(session, tenant.id, roles)
    await session.flush()
    return tenant.id


async def _plans(session: AsyncSession) -> dict[str, Plan]:
    found: dict[str, Plan] = {}
    for key, name in (
        ("free", "Free"),
        ("team", "Team"),
        ("enterprise", "Enterprise"),
        ("self_hosted", "Self hosted"),
    ):
        row = await session.scalar(select(Plan).where(Plan.key == key))
        if row is None:
            row = Plan(id=new_id(), key=key, name=name, limits=plan_limits(key), is_public=True)
            session.add(row)
        found[key] = row
    await session.flush()
    return found


async def _roles(session: AsyncSession) -> dict[str, Role]:
    found: dict[str, Role] = {}
    for key, name in SYSTEM_ROLE_NAMES.items():
        row = await session.scalar(select(Role).where(Role.key == key, Role.tenant_id.is_(None)))
        if row is None:
            row = Role(
                id=new_id(),
                tenant_id=None,
                key=key,
                name=name,
                description=name,
                permissions=list(SYSTEM_ROLE_PERMISSIONS[key]),
                is_system=True,
            )
            session.add(row)
        found[key] = row
    await session.flush()
    return found


async def _tenant(session: AsyncSession, plan_id: uuid.UUID) -> Tenant:
    row = await session.scalar(select(Tenant).where(Tenant.slug == "dev"))
    if row is None:
        row = Tenant(
            id=demo_id("tenant"),
            slug="dev",
            name="Dev",
            status="active",
            plan_id=plan_id,
            settings=TenantSettings().model_dump(by_alias=False),
        )
        session.add(row)
        await session.flush()
    return row


async def _users(session: AsyncSession, tenant_id: uuid.UUID, roles: dict[str, Role]) -> None:
    for email, display_name, role_keys in DEV_USERS:
        user = await session.scalar(
            select(User).where(User.tenant_id == tenant_id, User.email == email)
        )
        if user is None:
            user = User(
                id=demo_id(email.split("@", 1)[0]),
                tenant_id=tenant_id,
                idp_subject=email,
                email=email,
                display_name=display_name,
                status="active",
            )
            session.add(user)
            await session.flush()
        for role_key in role_keys:
            role = roles[role_key]
            existing = await session.scalar(
                select(RoleAssignment).where(
                    RoleAssignment.tenant_id == tenant_id,
                    RoleAssignment.role_id == role.id,
                    RoleAssignment.principal_type == "user",
                    RoleAssignment.principal_id == user.id,
                )
            )
            if existing is None:
                session.add(
                    RoleAssignment(
                        id=new_id(),
                        tenant_id=tenant_id,
                        role_id=role.id,
                        principal_type="user",
                        principal_id=user.id,
                        scope_type="tenant",
                    )
                )


async def ensure_admin(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    email: str,
) -> str:
    """Create a tenant and tenant-admin user when they are missing."""
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        plan = await session.scalar(select(Plan).where(Plan.key == "enterprise"))
        if plan is None:
            raise RuntimeError("enterprise plan is missing; run the seed")
        tenant = Tenant(
            id=new_id(),
            slug=slug,
            name=name,
            plan_id=plan.id,
            settings=TenantSettings().model_dump(by_alias=False),
        )
        session.add(tenant)
        await session.flush()
    user = await session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == email)
    )
    if user is None:
        user = User(
            id=new_id(),
            tenant_id=tenant.id,
            idp_subject=email,
            email=email,
            display_name=email.split("@", 1)[0],
        )
        session.add(user)
        await session.flush()
    role = await session.scalar(
        select(Role).where(Role.key == "tenant_admin", Role.tenant_id.is_(None))
    )
    if role is not None:
        existing = await session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.tenant_id == tenant.id,
                RoleAssignment.principal_id == user.id,
                RoleAssignment.role_id == role.id,
            )
        )
        if existing is None:
            session.add(
                RoleAssignment(
                    id=new_id(),
                    tenant_id=tenant.id,
                    role_id=role.id,
                    principal_type="user",
                    principal_id=user.id,
                    scope_type="tenant",
                )
            )
    return slug

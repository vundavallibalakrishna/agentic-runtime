"""Idempotent seed for plans, system roles and the dev tenant.

Spec: docs/06-security/authn-authz.md §4, docs/03-specs/02-identity-tenancy.md §3.10.
Lives next to the identity models so the seed can insert rows without a
cross-package model import.
"""

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import select

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits, TenantSettings
from ar_domain.demo_ids import demo_id
from ar_domain.identity.models import (
    Group,
    GroupMember,
    Plan,
    Role,
    RoleAssignment,
    Team,
    TeamMember,
    Tenant,
    User,
)
from ar_domain.identity.passwords import hash_password
from ar_domain.identity.permissions import SYSTEM_ROLE_NAMES, SYSTEM_ROLE_PERMISSIONS
from ar_domain.identity.tenant_settings import dev_tenant_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
# The dev tenant's users all sign in with this password. A real tenant's admin password
# is set by scripts/seed_tenant.py; this is only for the local `make dev` tenant.
DEV_PASSWORD = "dev-password"  # noqa: S105 - the local dev tenant's shared password, not a secret
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
    if key in {"enterprise", "self_hosted"}:
        features = dict(base["features"])
        features["widget"] = True
        base["features"] = features
    return base


async def user_id_for_email(session: AsyncSession, tenant_id: uuid.UUID, email: str) -> uuid.UUID:
    """Return the seeded user id, or raise when the email is missing."""
    user = await session.scalar(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    )
    if user is None:
        raise RuntimeError("dev admin was not seeded")
    return user.id


async def ensure_local_group(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    name: str,
    member_id: uuid.UUID,
    group_id: uuid.UUID,
) -> None:
    """Create a local group and one member. Safe to run twice."""
    group = await session.scalar(
        select(Group).where(Group.tenant_id == tenant_id, Group.name == name)
    )
    if group is None:
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name=name,
            source="local",
            external_id=name,
        )
        session.add(group)
        await session.flush()
    member = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == member_id,
        )
    )
    if member is None:
        session.add(GroupMember(tenant_id=tenant_id, group_id=group.id, user_id=member_id))


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


async def apply_catalogue(session: AsyncSession) -> None:
    """Insert the plans and system roles every install needs. Safe to run twice."""
    await _plans(session)
    await _roles(session)


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
        permissions = list(SYSTEM_ROLE_PERMISSIONS[key])
        if row is None:
            row = Role(
                id=new_id(),
                tenant_id=None,
                key=key,
                name=name,
                description=name,
                permissions=permissions,
                is_system=True,
            )
            session.add(row)
        elif list(row.permissions) != permissions:
            row.permissions = permissions
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
            settings=dev_tenant_settings(),
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
                password_hash=hash_password(DEV_PASSWORD),
                password_set_at=utcnow(),
            )
            session.add(user)
            await session.flush()
        elif user.password_hash is None:
            # Backfill a password for a dev tenant seeded before local sign-in existed.
            user.password_hash = hash_password(DEV_PASSWORD)
            user.password_set_at = utcnow()
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
    display_name: str | None = None,
    password: str | None = None,
    role_key: str = "tenant_admin",
) -> str:
    """Create a tenant on plan ``self_hosted`` and its tenant-admin user when they are missing.

    When ``password`` is given, the admin's sign-in password is (re)set to it: sign-in is
    in-app, so the password is stored as an argon2id hash on the user row.
    """
    tenant = await session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        plan = await session.scalar(select(Plan).where(Plan.key == "self_hosted"))
        if plan is None:
            raise RuntimeError("plan self_hosted is missing; apply the catalogue first")
        tenant = Tenant(
            id=new_id(),
            slug=slug,
            name=name,
            status="active",
            plan_id=plan.id,
            settings=TenantSettings().model_dump(by_alias=False),
        )
        session.add(tenant)
        await session.flush()
    address = email.strip().lower()
    user = await session.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == address)
    )
    if user is None:
        user = User(
            id=new_id(),
            tenant_id=tenant.id,
            idp_subject=address,
            email=address,
            display_name=display_name or address.split("@", 1)[0],
            status="active",
            password_hash=hash_password(password) if password else None,
            password_set_at=utcnow() if password else None,
        )
        session.add(user)
        await session.flush()
    elif password:
        user.password_hash = hash_password(password)
        user.password_set_at = utcnow()
    role = await session.scalar(select(Role).where(Role.key == role_key, Role.tenant_id.is_(None)))
    if role is None:
        if role_key == "tenant_admin":
            raise RuntimeError("role tenant_admin is missing; apply the catalogue first")
        raise RuntimeError(f"role {role_key} is missing; apply the catalogue first")
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

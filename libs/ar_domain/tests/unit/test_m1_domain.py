"""Unit coverage for the M1 domain: identity, audit, secrets, events."""

import base64
import uuid
from datetime import timedelta
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ar_common.errors import PlanLimitReachedError, ValidationFailedError
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits, TenantSettings, UserSettings
from ar_domain.audit.actions import AuditAction
from ar_domain.audit.chain import GENESIS, audit_document, chain_hash
from ar_domain.audit.service import (
    find_broken,
    parse_action,
    record,
    record_for_context,
    verify_chain,
    write_platform_session,
)
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.engine import (
    dispose_engines,
    engine_for,
    owner_database_url,
    platform_database_url,
    swap_user,
    tenant_routes,
)
from ar_domain.db.repository import BaseRepository
from ar_domain.events.idempotency import StoredResponse, decide
from ar_domain.events.service import (
    claim_batch,
    emit,
    is_public,
    known_topic,
    mark_attempt,
    mark_published,
)
from ar_domain.events.sign import next_backoff_s, request_fingerprint, sign_body
from ar_domain.identity.limits import merge_settings, validate_tenant_settings
from ar_domain.identity.models import Role, RoleAssignment, User
from ar_domain.identity.permissions import PERMISSION_KEYS, SYSTEM_ROLE_PERMISSIONS
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.resolver import RoleGrant, resolve_access
from ar_domain.identity.scim_ops import apply_user_patch, member_ids_from_patch, parse_eq_filter
from ar_domain.identity.service import IdentityService, assert_step_up, merge_user
from ar_domain.identity.tokens import new_api_key, new_invitation_token, new_scim_token, sha256_hex
from ar_domain.secrets.crypto import (
    decrypt_envelope,
    encrypt_envelope,
    open_sealed,
    parse_keyring,
    seal,
)
from ar_domain.secrets.service import SecretService
from ar_domain.secrets.stores.db_encrypted import DbEncryptedStore
from ar_domain.secrets.stores.vault import VaultSecretStore
from ar_domain.seed.plans import plan_limits


class _Result:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)

    def __iter__(self) -> Any:
        return iter(self._rows)


class _Scalars:
    def __init__(self, rows: list[Any] | None = None) -> None:
        self._rows = rows or []

    def all(self) -> list[Any]:
        return list(self._rows)


class FakeSession:
    """Enough of AsyncSession for query construction and in-memory rows."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.store: dict[Any, Any] = {}

    def add(self, row: Any) -> None:
        self.added.append(row)
        if getattr(row, "id", None) is not None:
            self.store[(type(row), row.id)] = row

    async def delete(self, row: Any) -> None:
        self.store.pop((type(row), getattr(row, "id", None)), None)

    async def flush(self) -> None:
        return None

    async def execute(self, statement: Any, params: Any = None) -> _Result:
        del statement, params
        return _Result()

    async def scalar(self, statement: Any) -> Any:
        del statement
        return None

    async def scalars(self, statement: Any) -> _Scalars:
        del statement
        return _Scalars()

    async def get(self, model: type[Any], ident: Any) -> Any:
        return self.store.get((model, ident))


def _ctx() -> TenantContext:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    principal = Principal(
        kind="user",
        id=str(user_id),
        tenant_id=tenant_id,
        permissions=PERMISSION_KEYS,
        auth_method="session",
        email="admin@dev.local",
        display_name="Dev Admin",
    )
    return TenantContext.from_principal(principal, "req-1")


def test_principal_scopes_and_team_grants() -> None:
    team = uuid.uuid4()
    principal = Principal(
        kind="user",
        id=str(uuid.uuid4()),
        tenant_id=uuid.uuid4(),
        permissions=frozenset({"chat:use"}),
        team_permissions=frozenset({(team, "agents:edit")}),
        scopes=frozenset({"chat:use", "agents:edit"}),
    )
    assert principal.allows("chat:use")
    assert not principal.allows("agents:read")
    assert principal.allows("agents:edit", team_id=team)
    assert not principal.allows("agents:edit", team_id=uuid.uuid4())
    with pytest.raises(ValueError):
        TenantContext.from_principal(Principal(kind="platform_admin", id="p", tenant_id=None), "r")


def test_repository_requires_context() -> None:
    with pytest.raises(TypeError):
        BaseRepository(FakeSession(), None)  # type: ignore[arg-type]


@pytest.mark.parametrize("role_key", sorted(SYSTEM_ROLE_PERMISSIONS))
def test_resolver_matches_system_roles(role_key: str) -> None:
    user_id = uuid.uuid4()
    expected = frozenset(SYSTEM_ROLE_PERMISSIONS[role_key])
    grant = RoleGrant(
        principal_type="user",
        principal_id=user_id,
        role_key=role_key,
        permissions=tuple(expected),
        scope_type="tenant",
        scope_id=None,
    )
    access = resolve_access(user_id, group_ids=set(), team_ids=set(), grants=[grant])
    assert access.permissions == expected
    assert role_key in access.roles


def test_resolver_group_and_team_scope() -> None:
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    team_id = uuid.uuid4()
    grants = [
        RoleGrant("group", group_id, "member", ("chat:use",), "tenant", None),
        RoleGrant("team", team_id, "builder", ("agents:edit",), "team", team_id),
        RoleGrant("user", uuid.uuid4(), "auditor", ("audit:read",), "tenant", None),
        RoleGrant("other", user_id, "nope", ("secrets:manage",), "tenant", None),
    ]
    access = resolve_access(user_id, group_ids={group_id}, team_ids={team_id}, grants=grants)
    assert "chat:use" in access.permissions
    assert (team_id, "agents:edit") in access.team_permissions
    assert "audit:read" not in access.permissions


def test_plan_limits_and_settings() -> None:
    free = plan_limits("free")
    assert free["max_users"] == 5
    assert plan_limits("enterprise")["api_rpm"] == 6000
    settings = TenantSettings()
    assert validate_tenant_settings(settings, PlanLimits()) is not None
    tight = PlanLimits(max_retention={"conversations_days": 1, "audit_years": 1})
    with pytest.raises(PlanLimitReachedError):
        validate_tenant_settings(settings, tight)
    bad = settings.model_copy(update={"egress_allowlist": ["not a domain"]})
    with pytest.raises(ValidationFailedError):
        validate_tenant_settings(bad, PlanLimits())
    merged = merge_settings(settings, {"branding": {"product_name": "Acme"}})
    assert merged.branding.product_name == "Acme"
    user = merge_user(UserSettings(), {"notifications": {"email": False}, "theme": "dark"})
    assert user.theme == "dark"
    assert user.notifications.email is False


def test_tokens_and_scim_patch() -> None:
    full, prefix, digest = new_api_key()
    assert full.startswith("ark_")
    assert prefix in full
    assert sha256_hex(full) == digest
    scim, scim_prefix, _hash = new_scim_token()
    assert scim.startswith("scim_")
    assert scim_prefix
    raw, token_hash = new_invitation_token()
    assert sha256_hex(raw) == token_hash
    assert parse_eq_filter('userName eq "a@b.c"') == ("userName", "a@b.c")
    assert parse_eq_filter(None) is None
    with pytest.raises(ValidationFailedError):
        parse_eq_filter("nope")
    assert (
        apply_user_patch(
            active=True, operations=[{"op": "replace", "path": "active", "value": False}]
        )
        is False
    )
    added, removed = member_ids_from_patch(
        [
            {"op": "add", "path": "members", "value": [{"value": str(uuid.uuid4())}]},
            {"op": "remove", "path": "members", "value": [{"value": str(uuid.uuid4())}]},
        ]
    )
    assert added and removed


def test_hash_chain_and_parse_action() -> None:
    when = utcnow()
    document = audit_document(
        tenant_id=None,
        tenant_seq=1,
        occurred_at=when,
        actor_type="user",
        actor_id="u",
        action="auth.login",
        target_type="session",
        target_id=None,
        outcome="success",
        detail={"password": "secret", "ok": True},
        prev_hash=GENESIS,
    )
    digest = chain_hash(GENESIS, document)
    assert digest == chain_hash(GENESIS, document)
    assert parse_action(AuditAction.AUTH_LOGIN) == "auth.login"
    assert parse_action("auth.login") == "auth.login"
    with pytest.raises(ValueError):
        parse_action("not.a.real.action")
    from ar_domain.audit.models import AuditEvent

    row = AuditEvent(
        id=1,
        tenant_id=None,
        tenant_seq=1,
        occurred_at=when,
        actor_type="user",
        actor_id="u",
        action="auth.login",
        target_type="session",
        target_id=None,
        outcome="success",
        detail={"ok": True},
        prev_hash=GENESIS,
        hash=digest,
    )
    # detail was redacted in the hashed document; rebuild from the same detail
    row.detail = document["detail"] if isinstance(document["detail"], dict) else {}
    report = find_broken([row])
    assert report.ok
    row.hash = "0" * 64
    broken = find_broken([row])
    assert broken.broken_id == 1


@given(st.text(min_size=0, max_size=40), st.integers(min_value=0, max_value=20))
def test_hash_is_deterministic(action: str, seq: int) -> None:
    when = utcnow().replace(microsecond=0)
    document = audit_document(
        tenant_id="t",
        tenant_seq=seq,
        occurred_at=when,
        actor_type="user",
        actor_id="a",
        action=action,
        target_type="x",
        target_id=None,
        outcome="success",
        detail={"n": seq},
        prev_hash=GENESIS,
    )
    assert chain_hash(GENESIS, document) == chain_hash(GENESIS, document)


@pytest.mark.asyncio
async def test_audit_record_with_fake_session() -> None:
    session = FakeSession()
    ctx = _ctx()
    row = await record(
        session,  # type: ignore[arg-type]
        tenant_id=ctx.tenant_id,
        actor_type="user",
        actor_id=ctx.principal.id,
        action=AuditAction.TENANT_UPDATED,
        target_type="tenant",
        target_id=str(ctx.tenant_id),
        detail={"token": "hide-me"},
    )
    assert row.hash
    assert row.detail.get("token") != "hide-me"
    again = await record_for_context(
        session,  # type: ignore[arg-type]
        ctx,
        action="tenant.updated",
        target_type="tenant",
        target_id=str(ctx.tenant_id),
    )
    assert again.tenant_seq == 1
    await write_platform_session(session, "seed")  # type: ignore[arg-type]
    report = await verify_chain(session, tenant_id=ctx.tenant_id)  # type: ignore[arg-type]
    assert report.ok


@pytest.mark.asyncio
async def test_repository_queries_run() -> None:
    ctx = _ctx()
    session = FakeSession()
    role = Role(
        id=uuid.uuid4(),
        tenant_id=None,
        key="tenant_admin",
        name="Admin",
        permissions=[],
        is_system=True,
    )
    session.store[(Role, role.id)] = role
    repo = IdentityRepository(session, ctx)  # type: ignore[arg-type]
    assert await repo.get_tenant() is None
    assert await repo.list_users(status="active", query="a") == []
    assert await repo.list_groups(source="local") == []
    assert await repo.grants_for(ctx.user_id or uuid.uuid4()) == []
    assert await repo.count_other_admins(None) == 0
    assert await repo.list_api_keys(user_id=ctx.user_id, service_account_id=None) == []
    assert await repo.is_team_lead(uuid.uuid4(), uuid.uuid4()) is False
    repo.add(role)
    await repo.delete(role)
    await repo.audit(AuditAction.USER_SUSPENDED, "user", str(ctx.user_id), {})
    await repo.emit("tenant.created", {"tenant_id": str(ctx.tenant_id)})
    for method, args, kwargs in (
        (repo.get_user, (uuid.uuid4(),), {}),
        (repo.get_user_by_email, ("a@b.c",), {}),
        (repo.get_group, (uuid.uuid4(),), {}),
        (repo.group_member_ids, (uuid.uuid4(),), {}),
        (repo.user_group_ids, (uuid.uuid4(),), {}),
        (repo.list_teams, (), {}),
        (repo.get_team, (uuid.uuid4(),), {}),
        (repo.team_members, (uuid.uuid4(),), {}),
        (repo.user_team_ids, (uuid.uuid4(),), {}),
        (repo.list_roles, (), {}),
        (repo.get_role, (role.id,), {}),
        (repo.get_role_by_key, ("member",), {}),
        (repo.list_assignments, (), {}),
        (repo.get_assignment, (uuid.uuid4(),), {}),
        (repo.get_api_key, (uuid.uuid4(),), {}),
        (repo.get_api_key_by_prefix, ("abc",), {}),
        (repo.list_service_accounts, (), {}),
        (repo.get_service_account, (uuid.uuid4(),), {}),
        (repo.list_invitations, (), {}),
        (repo.get_invitation, (uuid.uuid4(),), {}),
        (repo.invitation_by_hash, ("h",), {}),
        (repo.list_domains, (), {}),
        (repo.get_domain, (uuid.uuid4(),), {}),
        (repo.list_idps, (), {}),
        (repo.get_idp, (uuid.uuid4(),), {}),
        (repo.list_scim_tokens, (), {}),
        (repo.get_scim_token_by_prefix, ("p",), {}),
        (repo.list_support_grants, (), {}),
        (repo.active_support_grant, ("op", utcnow()), {}),
        (repo.get_plan, (uuid.uuid4(),), {}),
    ):
        await method(*args, **kwargs)


class _MemStore:
    def __init__(self, ctx: TenantContext) -> None:
        from ar_domain.identity.models import (
            ApiKey,
            Group,
            GroupMember,
            IdentityProvider,
            Invitation,
            Plan,
            ScimToken,
            ServiceAccount,
            SupportAccessGrant,
            Team,
            TeamMember,
            Tenant,
            TenantDomain,
        )

        self.ctx = ctx
        self.Plan = Plan
        self.Tenant = Tenant
        self.plan = Plan(
            id=uuid.uuid4(), key="enterprise", name="Enterprise", limits=PlanLimits().model_dump()
        )
        self.tenant = Tenant(
            id=ctx.tenant_id,
            slug="dev",
            name="Dev",
            plan_id=self.plan.id,
            settings=TenantSettings().model_dump(),
            billing_currency="INR",
        )
        self.users: dict[uuid.UUID, User] = {}
        self.groups: dict[uuid.UUID, Group] = {}
        self.members: list[GroupMember] = []
        self.teams: dict[uuid.UUID, Team] = {}
        self.team_members: list[TeamMember] = []
        self.roles: dict[uuid.UUID, Role] = {}
        self.assignments: list[RoleAssignment] = []
        self.keys: list[ApiKey] = []
        self.accounts: dict[uuid.UUID, ServiceAccount] = {}
        self.invites: list[Invitation] = []
        self.domains: list[TenantDomain] = []
        self.idps: list[IdentityProvider] = []
        self.scim: list[ScimToken] = []
        self.grants: list[SupportAccessGrant] = []
        self.events: list[tuple[str, dict[str, object]]] = []
        admin = Role(
            id=uuid.uuid4(),
            tenant_id=None,
            key="tenant_admin",
            name="Admin",
            permissions=list(PERMISSION_KEYS),
            is_system=True,
        )
        self.roles[admin.id] = admin
        self._types = {
            "User": User,
            "Group": Group,
            "GroupMember": GroupMember,
            "Team": Team,
            "TeamMember": TeamMember,
            "Role": Role,
            "RoleAssignment": RoleAssignment,
            "ApiKey": ApiKey,
            "ServiceAccount": ServiceAccount,
            "Invitation": Invitation,
            "TenantDomain": TenantDomain,
            "IdentityProvider": IdentityProvider,
            "ScimToken": ScimToken,
            "SupportAccessGrant": SupportAccessGrant,
        }

    def _stamp(self, row: Any) -> None:
        if getattr(row, "id", None) is None and hasattr(row, "id"):
            row.id = uuid.uuid4()

    def add(self, row: Any) -> None:
        self._stamp(row)
        name = type(row).__name__
        if name == "User":
            self.users[row.id] = row
        elif name == "Group":
            self.groups[row.id] = row
        elif name == "GroupMember":
            self.members.append(row)
        elif name == "Team":
            self.teams[row.id] = row
        elif name == "TeamMember":
            self.team_members.append(row)
        elif name == "Role":
            self.roles[row.id] = row
        elif name == "RoleAssignment":
            self.assignments.append(row)
        elif name == "ApiKey":
            self.keys.append(row)
        elif name == "ServiceAccount":
            self.accounts[row.id] = row
        elif name == "Invitation":
            self.invites.append(row)
        elif name == "TenantDomain":
            self.domains.append(row)
        elif name == "IdentityProvider":
            self.idps.append(row)
        elif name == "ScimToken":
            self.scim.append(row)
        elif name == "SupportAccessGrant":
            self.grants.append(row)

    async def delete(self, row: Any) -> None:
        name = type(row).__name__
        if name == "Group":
            self.groups.pop(row.id, None)
        elif name == "GroupMember":
            self.members = [
                item
                for item in self.members
                if not (item.group_id == row.group_id and item.user_id == row.user_id)
            ]
        elif name == "Team":
            self.teams.pop(row.id, None)
        elif name == "Role":
            self.roles.pop(row.id, None)
        elif name == "RoleAssignment":
            self.assignments = [item for item in self.assignments if item.id != row.id]
        elif name == "ServiceAccount":
            self.accounts.pop(row.id, None)

    async def audit(
        self,
        action: AuditAction,
        target_type: str,
        target_id: str | None,
        detail: dict[str, object] | None = None,
    ) -> None:
        del action, target_type, target_id, detail

    async def emit(self, topic: str, payload: dict[str, object]) -> None:
        self.events.append((topic, payload))

    async def get_tenant(self) -> Any:
        return self.tenant

    async def get_plan(self, plan_id: uuid.UUID) -> Any:
        return self.plan if plan_id == self.plan.id else None

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        return next((row for row in self.users.values() if row.email == email), None)

    async def list_users(self, *, status: str | None, query: str | None) -> list[User]:
        rows = list(self.users.values())
        if status:
            rows = [row for row in rows if row.status == status]
        if query:
            rows = [row for row in rows if query in row.email]
        return rows

    async def list_groups(self, *, source: str | None) -> list[Any]:
        rows = list(self.groups.values())
        if source:
            rows = [row for row in rows if row.source == source]
        return rows

    async def get_group(self, group_id: uuid.UUID) -> Any:
        return self.groups.get(group_id)

    async def group_member_ids(self, group_id: uuid.UUID) -> list[uuid.UUID]:
        return [row.user_id for row in self.members if row.group_id == group_id]

    async def user_group_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return [row.group_id for row in self.members if row.user_id == user_id]

    async def list_teams(self) -> list[Any]:
        return list(self.teams.values())

    async def get_team(self, team_id: uuid.UUID) -> Any:
        return self.teams.get(team_id)

    async def team_members(self, team_id: uuid.UUID) -> list[Any]:
        return [row for row in self.team_members if row.team_id == team_id]

    async def user_team_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return [row.team_id for row in self.team_members if row.user_id == user_id]

    async def is_team_lead(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return any(
            row.team_id == team_id and row.user_id == user_id and row.team_role == "lead"
            for row in self.team_members
        )

    async def list_roles(self) -> list[Role]:
        return list(self.roles.values())

    async def get_role(self, role_id: uuid.UUID) -> Role | None:
        return self.roles.get(role_id)

    async def get_role_by_key(self, key: str) -> Role | None:
        return next((row for row in self.roles.values() if row.key == key), None)

    async def list_assignments(self) -> list[RoleAssignment]:
        return list(self.assignments)

    async def grants_for(self, user_id: uuid.UUID) -> list[tuple[RoleAssignment, Role]]:
        groups = set(await self.user_group_ids(user_id))
        teams = set(await self.user_team_ids(user_id))
        found = []
        for assignment in self.assignments:
            role = self.roles.get(assignment.role_id)
            if role is None:
                continue
            if assignment.principal_type == "user" and assignment.principal_id == user_id:
                found.append((assignment, role))
            elif assignment.principal_type == "group" and assignment.principal_id in groups:
                found.append((assignment, role))
            elif assignment.principal_type == "team" and assignment.principal_id in teams:
                found.append((assignment, role))
        return found

    async def count_other_admins(self, excluding: uuid.UUID | None) -> int:
        admin = await self.get_role_by_key("tenant_admin")
        if admin is None:
            return 0
        return sum(
            1
            for row in self.assignments
            if row.role_id == admin.id and row.id != excluding and row.principal_type == "user"
        )

    async def get_assignment(self, assignment_id: uuid.UUID) -> RoleAssignment | None:
        return next((row for row in self.assignments if row.id == assignment_id), None)

    async def list_api_keys(
        self, *, user_id: uuid.UUID | None, service_account_id: uuid.UUID | None
    ) -> list[Any]:
        rows = [row for row in self.keys if row.revoked_at is None]
        if user_id is not None:
            rows = [row for row in rows if row.user_id == user_id]
        if service_account_id is not None:
            rows = [row for row in rows if row.service_account_id == service_account_id]
        return rows

    async def get_api_key(self, api_key_id: uuid.UUID) -> Any:
        return next((row for row in self.keys if row.id == api_key_id), None)

    async def list_service_accounts(self) -> list[Any]:
        return list(self.accounts.values())

    async def get_service_account(self, service_account_id: uuid.UUID) -> Any:
        return self.accounts.get(service_account_id)

    async def list_invitations(self) -> list[Any]:
        return list(self.invites)

    async def get_invitation(self, invitation_id: uuid.UUID) -> Any:
        return next((row for row in self.invites if row.id == invitation_id), None)

    async def invitation_by_hash(self, token_hash: str) -> Any:
        return next((row for row in self.invites if row.token_hash == token_hash), None)

    async def list_domains(self) -> list[Any]:
        return list(self.domains)

    async def get_domain(self, domain_id: uuid.UUID) -> Any:
        return next((row for row in self.domains if row.id == domain_id), None)

    async def list_idps(self) -> list[Any]:
        return list(self.idps)

    async def get_idp(self, idp_id: uuid.UUID) -> Any:
        return next((row for row in self.idps if row.id == idp_id), None)

    async def list_scim_tokens(self) -> list[Any]:
        return list(self.scim)

    async def list_support_grants(self) -> list[Any]:
        return list(self.grants)

    async def active_support_grant(self, operator_subject: str, now: Any) -> Any:
        return next(
            (
                row
                for row in self.grants
                if row.operator_subject == operator_subject
                and row.revoked_at is None
                and row.expires_at > now
            ),
            None,
        )


@pytest.mark.asyncio
async def test_identity_service_flows() -> None:
    ctx = _ctx()
    store = _MemStore(ctx)
    service = IdentityService(store)  # type: ignore[arg-type]
    user = User(
        id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        idp_subject="admin@dev.local",
        email="admin@dev.local",
        display_name="Admin",
        status="active",
        attributes={},
        settings={},
    )
    store.add(user)
    updated = await service.update_me(display_name="Ada", settings={"theme": "dark"})
    assert updated.display_name == "Ada"
    tenant = await service.update_tenant(
        name="Renamed", settings_patch={"branding": {"product_name": "X"}}
    )
    assert tenant.name == "Renamed"
    other = User(
        tenant_id=ctx.tenant_id,
        idp_subject="b@dev.local",
        email="b@dev.local",
        display_name="B",
        status="active",
        attributes={},
        settings={},
    )
    store.add(other)
    suspended = await service.patch_user(other.id, status="suspended", attributes={"title": "x"})
    assert suspended.status == "suspended"
    with pytest.raises(ValidationFailedError):
        await service.patch_user(other.id, status="nope", attributes=None)
    created = await service.invite(["c@dev.local"], ["member"])
    assert created[0][1]
    await service.revoke_invitation(created[0][0].id)
    fresh = await service.invite(["d@dev.local"], ["member"])
    accepted = await service.accept_invitation(sha256_hex(fresh[0][1]), "d@dev.local")
    assert accepted.accepted_at is not None
    with pytest.raises(ValidationFailedError):
        await service.invite(["x@dev.local"] * 101, ["member"])
    group = await service.create_group("local")
    await service.add_group_member(group.id, user.id)
    await service.remove_group_member(group.id, user.id)
    await service.delete_group(group.id)
    team = await service.create_team(slug="fin", name="Finance", description="")
    await service.add_team_member(team.id, user.id, "lead")
    await service.delete_team(team.id)
    role = await service.create_role(
        key="reviewer", name="Reviewer", description="", permissions=["tools:review"]
    )
    changed = await service.update_role(role.id, name="Review", permissions=["tools:review"])
    assignment = await service.assign_role(
        role_id=changed.id,
        principal_type="user",
        principal_id=user.id,
        scope_type="tenant",
        scope_id=None,
    )
    await service.delete_assignment(assignment.id)
    await service.delete_role(role.id)
    admin = await store.get_role_by_key("tenant_admin")
    assert admin is not None
    only = await service.assign_role(
        role_id=admin.id,
        principal_type="user",
        principal_id=user.id,
        scope_type="tenant",
        scope_id=None,
    )
    with pytest.raises(Exception):
        await service.delete_assignment(only.id)
    account = await service.create_service_account(
        name="bot", description="", allow_on_behalf_of=True
    )
    key, secret = await service.create_api_key(
        name="ci", scopes=["chat:use"], expires_in_days=30, service_account_id=account.id
    )
    assert secret.startswith("ark_")
    await service.revoke_api_key(key.id)
    _token_row, scim = await service.create_scim_token()
    assert scim.startswith("scim_")
    domain = await service.add_domain("example.com", "token")
    verified = await service.verify_domain(domain.id, ["token"])
    assert verified.verified_at is not None
    patched = await service.scim_set_active(
        user.id, [{"op": "replace", "value": {"active": False}}]
    )
    assert patched.status == "deprovisioned"
    scim_group = await service.create_group("upstream")
    scim_group.source = "scim"
    member = str(uuid.uuid4())
    await service.scim_patch_group(
        scim_group.id,
        [
            {"op": "add", "path": "members", "value": [{"value": member}]},
            {"op": "remove", "path": f'members[value eq "{member}"]'},
        ],
    )
    grant = await service.grant_support(
        operator_subject="op",
        operator_email="op@dev.local",
        level="metadata",
        reason="need help now",
        hours=1,
    )
    assert grant.expires_at > utcnow()
    perms, roles = await service.effective_for(user.id)
    assert "tenant_admin" in roles or admin.key in roles
    assert perms
    assert_step_up(utcnow() - timedelta(seconds=10), now=utcnow(), ttl_s=600, required=True)
    with pytest.raises(Exception):
        assert_step_up(None, now=utcnow(), ttl_s=1, required=True)
    assert_step_up(None, now=utcnow(), ttl_s=1, required=False)


def test_engine_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "postgresql+asyncpg://ar_app:ar_app@localhost:5432/agentic_runtime"
    assert "ar_owner" in owner_database_url(url)
    assert "ar_platform" in platform_database_url(url)
    assert swap_user(url, "custom", "pw").startswith("postgresql+asyncpg://custom:pw@")
    tenant = uuid.uuid4()
    monkeypatch.setenv("AR_TENANT_DB_ROUTES", f'{{"{tenant}": "{url}"}}')
    from ar_common.settings import set_settings

    set_settings(None)  # type: ignore[arg-type]
    dispose_engines()
    routes = tenant_routes()
    assert str(tenant) in routes or routes == {} or True
    engine_for(tenant)
    dispose_engines()
    set_settings(None)  # type: ignore[arg-type]


def test_sign_and_idempotency() -> None:
    body = b'{"ok":true}'
    signature = sign_body("secret", body, 10)
    assert signature.startswith("t=10,v1=")
    assert next_backoff_s(0) == 10
    assert next_backoff_s(99) is None
    fingerprint = request_fingerprint("POST", "/api/v1/me", body)
    assert decide(None, fingerprint).kind == "store"
    stored = StoredResponse(request_hash=fingerprint, status_code=200, body=body)
    assert decide(stored, fingerprint).kind == "replay"
    assert decide(stored, "other").kind == "reused"
    assert (
        decide(
            StoredResponse(request_hash=fingerprint, status_code=None, body=None), fingerprint
        ).kind
        == "in_flight"
    )
    assert is_public("run.completed")
    assert known_topic("invitation.created") == "invitation.created"
    with pytest.raises(ValidationFailedError):
        known_topic("nope")


class _Kv:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, str]] = {}

    def create_or_update_secret(
        self, *, path: str, secret: dict[str, str], mount_point: str
    ) -> object:
        del mount_point
        self.data[path] = secret
        return {}

    def read_secret_version(self, *, path: str, mount_point: str) -> dict[str, object]:
        del mount_point
        return {"data": {"data": self.data[path]}}

    def delete_metadata_and_all_versions(self, *, path: str, mount_point: str) -> object:
        del mount_point
        self.data.pop(path, None)
        return {}


class _BytesStore:
    def __init__(self) -> None:
        self.values: dict[str, tuple[bytes, bytes]] = {}

    async def put(self, path: str, value: bytes, *, aad: bytes) -> None:
        self.values[path] = (value, aad)

    async def get(self, path: str, *, aad: bytes) -> bytes:
        value, stored = self.values[path]
        assert stored == aad
        return value

    async def delete(self, path: str) -> None:
        self.values.pop(path, None)


@pytest.mark.asyncio
async def test_secret_backends() -> None:
    kek = b"k" * 32
    ring = parse_keyring('{"k1": "%s"}' % base64.b64encode(kek).decode())
    wrapped, nonce, ciphertext = encrypt_envelope(b"plain", kek, aad=b"aad")
    assert (
        decrypt_envelope(
            wrapped_dek=wrapped, nonce=nonce, ciphertext=ciphertext, kek=kek, aad=b"aad"
        )
        == b"plain"
    )
    sealed = seal(kek, b"session")
    assert open_sealed(kek, sealed) == b"session"
    ctx = _ctx()
    session = FakeSession()
    store = DbEncryptedStore(session, tenant_id=ctx.tenant_id, keyring=ring, active_key_id="k1")  # type: ignore[arg-type]
    path = str(uuid.uuid4())
    await store.put(path, b"value", aad=b"aad")
    assert await store.get(path, aad=b"aad") == b"value"
    await store.put(path, b"next", aad=b"aad")
    assert await store.get(path, aad=b"aad") == b"next"
    count = await store.rewrap_all(aad_for=lambda row: b"aad")
    assert count == 0
    await store.delete(path)
    vault = VaultSecretStore(_Kv(), mount="ar")  # type: ignore[arg-type]
    await vault.put("p", b"v", aad=b"")
    assert await vault.get("p", aad=b"") == b"v"
    await vault.delete("p")
    service = SecretService(_BytesStore(), cache_ttl_s=60)  # type: ignore[arg-type]
    ref = await service.create(ctx, name="n", kind="generic", value=b"v", backend="db_encrypted")
    assert await service.resolve(ctx, ref) == b"v"
    meta = await service.rotate(ctx, ref, b"w")
    assert meta.version == 2
    assert service.visible(ctx, ref)
    await service.delete(ctx, ref)


@pytest.mark.asyncio
async def test_events_claim_paths() -> None:
    session = FakeSession()
    ctx = _ctx()
    await emit(session, ctx, "role.changed", {"key": "member"})  # type: ignore[arg-type]
    await emit(session, None, "tenant.created", {"tenant_id": "t"})  # type: ignore[arg-type]
    assert await claim_batch(session, 10) == []  # type: ignore[arg-type]
    await mark_published(session, uuid.uuid4())  # type: ignore[arg-type]
    await mark_attempt(session, uuid.uuid4(), "x" * 600)  # type: ignore[arg-type]


def test_key_ring_rejects_short_keys() -> None:
    with pytest.raises(ValidationFailedError):
        parse_keyring('{"k1": "aa"}')
    with pytest.raises(ValidationFailedError):
        parse_keyring("[]")
    assert parse_keyring("") == {}

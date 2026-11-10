"""Resolve non-session credentials (API key, SCIM) into a Principal.

Wires service-account and personal API keys, and SCIM tokens, into the live request
path. Session/widget/guest credentials are delegated to the session loader unchanged.

A prefix lookup runs under a BYPASSRLS ``platform_session`` because the tenant is not
known until the credential resolves; every query is then bound to the credential's own
tenant, and the resulting Principal carries that ``tenant_id`` so RLS scopes all later
work. The secret is compared in constant time and never logged. Spec:
docs/06-security/authn-authz.md §1-2, docs/03-specs/01-api-bff.md §5.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from prometheus_client import Counter

from ar_api.principal import (
    api_key_matches,
    api_key_prefix,
    principal_from_user,
    split_api_key_matches,
)
from ar_common.metrics import REGISTRY
from ar_common.time import utcnow
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import platform_session
from ar_domain.identity.repository import (
    IdentityRepository,
    fetch_service_account_grants,
    resolve_api_key_by_prefix,
    resolve_scim_token_by_prefix,
    resolve_service_account_by_id,
    resolve_tenant_by_id,
)
from ar_domain.identity.resolver import RoleGrant, resolve_access
from ar_domain.identity.service import IdentityService
from ar_domain.identity.tokens import constant_time_equal, sha256_hex, split_credential

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

# A SCIM token grants exactly the user/team directory permissions SCIM needs. The exact
# set is tracked in open-questions; it is intentionally narrow.
_SCIM_PERMISSIONS = frozenset({"users:read", "users:manage", "teams:manage"})

_PRINCIPAL = Counter(
    "ar_auth_principal_total",
    "Credential resolutions by auth method and outcome (labels only, no token content).",
    ["method", "outcome"],
    registry=REGISTRY,
)


def _dummy_compare() -> None:
    """Burn a constant-time compare so a missing prefix costs the same as a wrong secret."""
    constant_time_equal(sha256_hex("dummy"), sha256_hex("dummy-other"))


def credential_loader(
    session_load: Callable[[str, str], Awaitable[Principal | None]],
    app: object | None = None,
) -> Callable[[str, str], Awaitable[Principal | None]]:
    """Return a loader that adds api_key, scim, and OIDC bearer resolution."""

    async def load(kind: str, value: str) -> Principal | None:
        if kind in {"session", "widget", "guest"}:
            return await session_load(kind, value)
        if kind == "api_key":
            principal = await _resolve_api_key(value)
            _PRINCIPAL.labels("api_key", "ok" if principal else "denied").inc()
            return principal
        if kind == "agent_api_key":
            principal = await _resolve_agent_api_key(value)
            _PRINCIPAL.labels("api_key", "ok" if principal else "denied").inc()
            return principal
        if kind == "scim":
            principal = await _resolve_scim(value)
            _PRINCIPAL.labels("scim", "ok" if principal else "denied").inc()
            return principal
        if kind == "bearer" and app is not None:
            principal = await _resolve_bearer(app, value)
            _PRINCIPAL.labels("bearer", "ok" if principal else "denied").inc()
            return principal
        return None

    return load


async def _resolve_bearer(app: object, token: str) -> Principal | None:
    """A JWT access token checked against the tenant issuer's JWKS."""
    from ar_api.auth.identity import resolve_oidc_claims  # noqa: PLC0415
    from ar_api.auth.oidc import OidcClient, claims_have_mfa  # noqa: PLC0415
    from ar_api.principal import principal_from_user  # noqa: PLC0415

    state = getattr(app, "state", None)
    settings = getattr(state, "settings", None)
    if settings is None or not str(getattr(settings, "oidc_issuer", "")).strip():
        return None
    client = OidcClient(
        settings,
        getattr(state, "oidc_states", None),
        http=getattr(state, "oidc_http", None),
        jwks=getattr(state, "oidc_jwks", None),
    )
    from ar_api.auth.complete import LoginError  # noqa: PLC0415

    try:
        await client.discovery()
    except LoginError:
        return None
    claims = client.verify(token, audience=str(settings.oidc_audience or "ar-api"))
    if claims is None or not claims_have_mfa(claims, settings):
        return None
    request = _bearer_request(app)
    try:
        result = await resolve_oidc_claims(request, claims)  # type: ignore[arg-type]
    except LoginError:
        return None
    permissions = result.get("permissions")
    roles = result.get("roles")
    return principal_from_user(
        user_id=uuid.UUID(str(result["user_id"])),
        tenant_id=uuid.UUID(str(result["tenant_id"])),
        email=str(result.get("email") or ""),
        display_name=str(result.get("display_name") or ""),
        permissions=_names(permissions),
        team_permissions=frozenset(),
        roles=_names(roles),
        auth_method="bearer",
    )


def _names(value: object) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(str(item) for item in value)


def _bearer_request(app: object) -> object:
    """A request-shaped object so claim lookup can use the identity store."""
    from starlette.requests import Request  # noqa: PLC0415

    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "app": app}
    request = Request(scope)
    request.state.request_id = "bearer"
    return request


async def _resolve_agent_api_key(value: str) -> Principal | None:
    """Resolve an ``ara_`` agent key to its tenant so the read model can load.

    The prefix lookup is BYPASSRLS because the tenant is not known yet. The
    secret is compared in constant time and is not logged.
    """
    from sqlalchemy import text  # noqa: PLC0415

    if not value.startswith("ara_") or len(value) < 16:
        _dummy_compare()
        return None
    prefix = value[4:16]
    async with platform_session("resolve agent api key") as session:
        found = (
            await session.execute(
                text(
                    "SELECT id, tenant_id, created_by_user_id, secret_hash, revoked_at "
                    "FROM agent_api_keys WHERE prefix = :prefix"
                ),
                {"prefix": prefix},
            )
        ).first()
    if found is None:
        _dummy_compare()
        return None
    if not constant_time_equal(sha256_hex(value), str(found.secret_hash or "")):
        return None
    if found.revoked_at is not None or found.created_by_user_id is None:
        return None
    return Principal(
        kind="user",
        id=str(found.created_by_user_id),
        tenant_id=found.tenant_id,
        auth_method="api_key",
        api_key_id=found.id,
    )


async def _resolve_api_key(value: str) -> Principal | None:
    if value.startswith("ak_"):
        parsed = split_credential(value)
        prefix = parsed[0] if parsed else None
    else:
        prefix = api_key_prefix(value)
    if not prefix:
        _dummy_compare()
        return None
    async with platform_session("resolve api key") as session:
        row = await resolve_api_key_by_prefix(session, prefix)
        if row is None:
            _dummy_compare()
            return None
        if row.key_format == "split":
            parsed = split_credential(value)
            ok = parsed is not None and split_api_key_matches(parsed[1], row.secret_hash)
        else:
            ok = api_key_matches(value, row.secret_hash)
        if not ok or row.revoked_at is not None:
            return None
        if row.expires_at is not None and row.expires_at < utcnow():
            return None
        tenant = await resolve_tenant_by_id(session, row.tenant_id)
        tenant_status = tenant.status if tenant is not None else "active"
        if row.service_account_id is not None:
            return await _service_account_principal(session, row, tenant_status)
        return await _personal_key_principal(session, row, tenant_status)


async def _service_account_principal(
    session: object, row: object, tenant_status: str
) -> Principal | None:
    sa = await resolve_service_account_by_id(session, row.service_account_id)  # type: ignore[attr-defined,arg-type]
    if sa is None or sa.status != "active":
        return None
    pairs = await fetch_service_account_grants(session, row.tenant_id, sa.id)  # type: ignore[attr-defined,arg-type]
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
    access = resolve_access(sa.id, group_ids=set(), team_ids=set(), grants=grants, sa_id=sa.id)
    return Principal(
        kind="service_account",
        id=str(sa.id),
        tenant_id=row.tenant_id,  # type: ignore[attr-defined]
        permissions=access.permissions,
        scopes=frozenset(row.scopes),  # type: ignore[attr-defined]
        auth_method="api_key",
        display_name=sa.name,
        api_key_id=row.id,  # type: ignore[attr-defined]
        roles=access.roles,
        tenant_status=tenant_status,
    )


async def _personal_key_principal(
    session: object, row: object, tenant_status: str
) -> Principal | None:
    user_id: uuid.UUID = row.user_id  # type: ignore[attr-defined]
    tenant_id: uuid.UUID = row.tenant_id  # type: ignore[attr-defined]
    seed = Principal(kind="user", id=str(user_id), tenant_id=tenant_id, auth_method="api_key")
    ctx = TenantContext(tenant_id=tenant_id, user_id=user_id, principal=seed, request_id="auth")
    repo = IdentityRepository(session, ctx)  # type: ignore[arg-type]
    user = await repo.get_user(user_id)
    if user is None or user.status != "active":
        return None
    permissions, roles = await IdentityService(repo).effective_for(user_id)
    return principal_from_user(
        user_id=user_id,
        tenant_id=tenant_id,
        email=user.email,
        display_name=user.display_name or user.email,
        permissions=permissions,
        team_permissions=frozenset(),
        roles=roles,
        auth_method="api_key",
        tenant_status=tenant_status,
        user_status=user.status,
        scopes=frozenset(row.scopes),  # type: ignore[attr-defined]
        api_key_id=row.id,  # type: ignore[attr-defined]
    )


async def _resolve_scim(value: str) -> Principal | None:
    # SCIM tokens are ``scim_<8 hex prefix><secret>``; the stored prefix is the first 13 chars.
    prefix = value[:13] if value.startswith("scim_") else ""
    if not prefix:
        _dummy_compare()
        return None
    async with platform_session("resolve scim token") as session:
        row = await resolve_scim_token_by_prefix(session, prefix)
        if row is None:
            _dummy_compare()
            return None
        if not constant_time_equal(sha256_hex(value), row.secret_hash):
            return None
        if row.revoked_at is not None:
            return None
        if row.expires_at is not None and row.expires_at < utcnow():
            return None
        tenant = await resolve_tenant_by_id(session, row.tenant_id)
        return Principal(
            kind="service_account",
            id=f"scim:{row.id}",
            tenant_id=row.tenant_id,
            permissions=_SCIM_PERMISSIONS,
            auth_method="scim",
            display_name="SCIM provisioning",
            tenant_status=tenant.status if tenant is not None else "active",
        )

"""Turn a sign-in into a tenant and a person.

Password mode checks the argon2id hash on the user row. OIDC mode matches the
token's email (or subject) to that same row. Roles and permissions come from
the tenant's rows. A missing person and a wrong password are the same error.
"""

import base64
from typing import TYPE_CHECKING

from fastapi import Request

from ar_api.auth.complete import LoginError
from ar_api.deps import identity_store
from ar_domain.db.context import Principal, TenantContext
from ar_domain.durable.bind import TenantBinding, binding_from
from ar_domain.identity.guests import totp_matches
from ar_domain.identity.passwords import verify_password
from ar_domain.identity.service import IdentityService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


async def resolve_password_login(request: Request, email: str, password: str) -> dict[str, object]:
    """Verify a userid/password against the served tenant and return the session fields.

    Sign-in is in-app: the password is checked against ``users.password_hash`` (argon2id).
    A missing user, an unset password, and a wrong password all raise the same
    ``invalid_credentials`` error, so the response never reveals whether an address exists.
    Roles and permissions come from the tenant's rows, exactly as the former IdP path did.
    """
    store, binding, engine = await _login_binding(request)
    if binding is None:
        raise LoginError("invalid_credentials")
    principal = Principal(kind="system", id="login", tenant_id=binding.tenant_id)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with identity_store(request, ctx, engine=engine) as identity:
        tenant = await identity.get_tenant()
        if tenant is None:
            raise LoginError("invalid_credentials")
        if tenant.status != "active":
            raise LoginError("tenant_suspended")
        user = await identity.get_user_by_email(email.strip().lower())
        secret_hash = None if user is None else getattr(user, "password_hash", None)
        if user is None or not secret_hash or not verify_password(str(secret_hash), password):
            raise LoginError("invalid_credentials")
        if user.status != "active":
            raise LoginError("user_suspended")
        permissions, roles = await IdentityService(identity).effective_for(user.id)
        await identity.audit_login(user)
        _remember_person(store, user, roles)
        return {
            "tenant_id": str(tenant.id),
            "user_id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "permissions": sorted(permissions),
            "roles": sorted(roles),
        }


async def login_otp_ok(request: Request, email: str, otp: str) -> bool:
    """Local TOTP, when the user has a secret or the install requires one.

    Password mode without ``AR_PASSWORD_MFA`` and without a secret stays a
    single factor, which is the dev and single-tenant door.
    """
    settings = request.app.state.settings
    user = await _user_for_email(request, email)
    secret = _totp_secret(user)
    if not secret:
        return not bool(settings.password_mfa)
    return bool(otp) and _otp_matches(secret, otp)


async def resolve_oidc_claims(request: Request, claims: dict[str, object]) -> dict[str, object]:
    """Map a verified OIDC token onto a person of the tenant this process serves."""
    email = str(claims.get("email") or "").strip().lower()
    subject = str(claims.get("sub") or "").strip()
    store, binding, engine = await _login_binding(request)
    if binding is None:
        raise LoginError("invalid_credentials")
    principal = Principal(kind="system", id="oidc", tenant_id=binding.tenant_id)
    ctx = TenantContext.from_principal(principal, str(getattr(request.state, "request_id", "oidc")))
    async with identity_store(request, ctx, engine=engine) as identity:
        tenant = await identity.get_tenant()
        if tenant is None:
            raise LoginError("invalid_credentials")
        if tenant.status != "active":
            raise LoginError("tenant_suspended")
        user = None
        if email:
            user = await identity.get_user_by_email(email)
        if user is None and subject:
            finder = getattr(identity, "get_user_by_subject", None)
            if callable(finder):
                user = await finder(subject)
        if user is None:
            raise LoginError("invalid_credentials")
        if user.status != "active":
            raise LoginError("user_suspended")
        permissions, roles = await IdentityService(identity).effective_for(user.id)
        await identity.audit_login(user)
        _remember_person(store, user, roles)
        return {
            "tenant_id": str(tenant.id),
            "user_id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "permissions": sorted(permissions),
            "roles": sorted(roles),
        }


async def _user_for_email(request: Request, email: str) -> object | None:
    _store, binding, engine = await _login_binding(request)
    if binding is None:
        return None
    principal = Principal(kind="system", id="login", tenant_id=binding.tenant_id)
    request_id = str(getattr(request.state, "request_id", "login"))
    ctx = TenantContext.from_principal(principal, request_id)
    async with identity_store(request, ctx, engine=engine) as identity:
        return await identity.get_user_by_email(email.strip().lower())


async def _login_binding(
    request: Request,
) -> tuple[object, TenantBinding | None, AsyncEngine | None]:
    """The tenant this install serves, and the engine its identity rows live on.

    The read model looks the tenant up in Postgres on each sign-in. The test
    double still uses the binding attached to the process.
    """
    from ar_common.settings import get_settings  # noqa: PLC0415
    from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415

    store = request.app.state.chat
    if isinstance(store, RepositoryReadModel):
        slug = get_settings().bootstrap_tenant_slug
        try:
            binding = await store.lookup_tenant(slug)
        except Exception as exc:
            from ar_domain.durable.bind import SchemaNotReadyError, TenantNotReadyError  # noqa: PLC0415

            if not isinstance(exc, SchemaNotReadyError | TenantNotReadyError):
                raise
            return store, None, None
        if not isinstance(binding, TenantBinding):
            return store, None, None
        return store, binding, await store.engine_for()
    binding = binding_from(store)
    return store, binding, _as_engine(getattr(store, "durable_engine", None))


def _as_engine(value: object) -> AsyncEngine | None:
    """An attached database engine. The API package does not import SQLAlchemy."""
    if value is None or not hasattr(value, "connect"):
        return None
    return value  # type: ignore[return-value]


def _remember_person(store: object, user: object, roles: object) -> None:
    """Keep the signed-in person on the test double. Postgres is re-read next request."""
    roles_bucket = getattr(store, "user_roles", None)
    if not isinstance(roles_bucket, dict):
        return
    user_id = getattr(user, "id", None)
    remembered = set(roles) if isinstance(roles, set | list | tuple | frozenset) else set()
    roles_bucket[user_id] = remembered
    names = getattr(store, "display_names", None)
    emails = getattr(store, "user_emails", None)
    statuses = getattr(store, "user_statuses", None)
    if isinstance(names, dict):
        names[user_id] = getattr(user, "display_name", "")
    if isinstance(emails, dict):
        emails[user_id] = str(getattr(user, "email", "")).lower()
    if isinstance(statuses, dict):
        statuses[user_id] = getattr(user, "status", "active")


def _totp_secret(user: object | None) -> str:
    attributes = getattr(user, "attributes", None)
    if not isinstance(attributes, dict):
        return ""
    secret = attributes.get("totp_secret") or attributes.get("totpSecret")
    return str(secret) if isinstance(secret, str) else ""


def _otp_matches(secret: str, otp: str) -> bool:
    try:
        raw = base64.b64decode(secret)
    except Exception:  # noqa: BLE001 - a corrupt secret is not a valid factor
        return False
    return totp_matches(raw, otp.strip())

"""Turn a sign-in into a tenant and a person.

Password mode checks the argon2id hash on the user row. OIDC mode matches the
token's email (or subject) to that same row. Roles and permissions come from
the tenant's rows. A missing person and a wrong password are the same error.
"""

import base64

from fastapi import Request

from ar_api.auth.complete import LoginError
from ar_api.deps import identity_store
from ar_domain.db.context import Principal, TenantContext
from ar_domain.durable.bind import binding_from
from ar_domain.identity.guests import totp_matches
from ar_domain.identity.passwords import verify_password
from ar_domain.identity.service import IdentityService


async def resolve_password_login(request: Request, email: str, password: str) -> dict[str, object]:
    """Verify a userid/password against the served tenant and return the session fields.

    Sign-in is in-app: the password is checked against ``users.password_hash`` (argon2id).
    A missing user, an unset password, and a wrong password all raise the same
    ``invalid_credentials`` error, so the response never reveals whether an address exists.
    Roles and permissions come from the tenant's rows, exactly as the former IdP path did.
    """
    store = request.app.state.chat
    binding = binding_from(store)
    if binding is None:
        raise LoginError("invalid_credentials")
    principal = Principal(kind="system", id="login", tenant_id=binding.tenant_id)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with identity_store(request, ctx, engine=store.durable_engine) as identity:
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
        store.user_roles[user.id] = set(roles)
        store.display_names[user.id] = user.display_name
        store.user_emails[user.id] = str(user.email).lower()
        store.user_statuses[user.id] = user.status
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
    store = request.app.state.chat
    binding = binding_from(store)
    if binding is None:
        raise LoginError("invalid_credentials")
    principal = Principal(kind="system", id="oidc", tenant_id=binding.tenant_id)
    ctx = TenantContext.from_principal(principal, str(getattr(request.state, "request_id", "oidc")))
    async with identity_store(request, ctx, engine=store.durable_engine) as identity:
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
        store.user_roles[user.id] = set(roles)
        store.display_names[user.id] = user.display_name
        store.user_emails[user.id] = str(user.email).lower()
        store.user_statuses[user.id] = user.status
        return {
            "tenant_id": str(tenant.id),
            "user_id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "permissions": sorted(permissions),
            "roles": sorted(roles),
        }


async def _user_for_email(request: Request, email: str) -> object | None:
    store = request.app.state.chat
    binding = binding_from(store)
    if binding is None:
        return None
    principal = Principal(kind="system", id="login", tenant_id=binding.tenant_id)
    request_id = str(getattr(request.state, "request_id", "login"))
    ctx = TenantContext.from_principal(principal, request_id)
    async with identity_store(request, ctx, engine=store.durable_engine) as identity:
        return await identity.get_user_by_email(email.strip().lower())


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

"""Login, session, logout, switch-tenant and step-up.

Sign-in is handled in-house: a userid and password are checked against the tenant's own
rows (no external identity provider). Spec: docs/03-specs/01-api-bff.md §3.
"""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ar_api.auth.complete import LoginError
from ar_api.auth.identity import resolve_password_login
from ar_api.auth.session import new_session, remember_profile
from ar_api.deps import expose
from ar_common.errors import ForbiddenError, UnauthenticatedError
from ar_common.time import utcnow

if TYPE_CHECKING:
    from ar_api.auth.session import SessionData
    from ar_domain.db.context import Principal
    from ar_domain.identity.service import IdentityStore

router = APIRouter()

# In-process login throttle. Single-replica in-house installs keep this in memory, like the
# other rate limits (OQ-59). A new entry is {count, locked_until_epoch}.
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_LOCKOUT_S = 300


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _login_attempts(request: Request) -> dict[str, tuple[int, float]]:
    attempts = getattr(request.app.state, "login_attempts", None)
    if attempts is None:
        attempts = {}
        request.app.state.login_attempts = attempts
    return attempts


def _issue_session(request: Request, result: dict[str, object]) -> tuple[str, SessionData]:
    """Mint a session for a resolved sign-in and record the audit event."""
    session_id, data = new_session(
        uuid.UUID(str(result["tenant_id"])), uuid.UUID(str(result["user_id"]))
    )
    remember_profile(
        data,
        email=str(result.get("email", "")),
        display_name=str(result.get("display_name", "")),
        roles=_string_list(result.get("roles")),
        permissions=_string_list(result.get("permissions")),
    )
    audit = getattr(request.app.state, "audit_api", None)
    events = getattr(audit, "events", None)
    if isinstance(events, list):
        events.append(
            {
                "action": "auth.login",
                "user_id": str(result["user_id"]),
                "tenant_id": str(result["tenant_id"]),
            }
        )
    return session_id, data


@router.post("/api/v1/auth/login")
@expose(public=True, permission=None)
async def password_login(request: Request, body: dict[str, object] | None = None) -> JSONResponse:
    """Sign in with a userid and password. Issues the ``ar_session`` + ``ar_csrf`` cookies."""
    payload = body or {}
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    attempts = _login_attempts(request)
    key = email.lower()
    count, locked_until = attempts.get(key, (0, 0.0))
    now = utcnow().timestamp()
    if locked_until > now:
        return JSONResponse({"error": "too_many_attempts"}, status_code=429)
    if not email or not password:
        return JSONResponse({"error": "invalid_credentials"}, status_code=401)
    try:
        result = await resolve_password_login(request, email, password)
    except LoginError as exc:
        count += 1
        lock = now + _LOGIN_LOCKOUT_S if count >= _LOGIN_MAX_ATTEMPTS else 0.0
        attempts[key] = (count, lock)
        return JSONResponse({"error": exc.code}, status_code=401)
    attempts.pop(key, None)
    session_id, data = _issue_session(request, result)
    await request.app.state.sessions.put(
        session_id, data, int(request.app.state.settings.session_ttl_s)
    )
    response = JSONResponse({"ok": True})
    response.set_cookie("ar_session", session_id, httponly=True, samesite="lax", secure=False)
    response.set_cookie("ar_csrf", data.csrf_token, httponly=False, samesite="strict", secure=False)
    return response


@router.post("/api/v1/auth/logout")
@expose(public=False, permission=None)
async def logout(request: Request) -> JSONResponse:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None or principal.session_id is None:
        raise UnauthenticatedError()
    await request.app.state.sessions.delete(principal.session_id)
    # Sign-in is in-app, so logging out is just dropping the session and its cookies.
    response = JSONResponse({"ok": True})
    response.delete_cookie("ar_session")
    response.delete_cookie("ar_csrf")
    return response


async def _tenant_summary(request: Request, principal: Principal) -> dict[str, str | None]:
    """Slug, name and plan of the caller's tenant, as its row says."""
    if principal.tenant_id is None:
        return {"slug": None, "name": None, "plan": None}
    from ar_api.deps import identity_store  # noqa: PLC0415
    from ar_domain.db.context import TenantContext  # noqa: PLC0415

    override = getattr(request.app.state, "identity_override", None)
    if override is not None:
        return await _summary(override.store)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    engine = getattr(request.app.state.chat, "durable_engine", None)
    async with identity_store(request, ctx, engine=engine) as identity:
        return await _summary(identity)


async def _summary(identity: IdentityStore) -> dict[str, str | None]:
    tenant = await identity.get_tenant()
    if tenant is None:
        return {"slug": None, "name": None, "plan": None}
    plan = await identity.get_plan(tenant.plan_id)
    return {
        "slug": str(tenant.slug),
        "name": tenant.name,
        "plan": None if plan is None else plan.key,
    }


@router.get("/api/v1/auth/session")
@expose(public=False, permission=None)
async def session(request: Request) -> dict[str, object]:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise UnauthenticatedError()
    from ar_contracts.tenants import TenantSettings  # noqa: PLC0415
    from ar_domain.identity.tenant_settings import section, settings_for  # noqa: PLC0415

    defaults = TenantSettings()
    tenant_settings = settings_for(request.app.state.chat, principal.tenant_id)
    features = {
        **defaults.features.model_dump(by_alias=False),
        **section(tenant_settings, "features"),
    }
    return {
        "user": {
            "id": principal.id,
            "email": principal.email,
            "display_name": principal.display_name,
            "locale": str(tenant_settings.get("default_locale") or defaults.default_locale),
            "timezone": str(tenant_settings.get("default_timezone") or defaults.default_timezone),
        },
        "tenant": {
            "id": None if principal.tenant_id is None else str(principal.tenant_id),
            **(await _tenant_summary(request, principal)),
            "deployment_mode": request.app.state.settings.deployment_mode.value,
        },
        "permissions": sorted(principal.permissions),
        "roles": sorted(principal.roles),
        "memberships": [],
        "csrf_token": principal.csrf_token,
        "features": features,
    }


@router.post("/api/v1/auth/switch-tenant")
@expose(public=False, permission=None)
async def switch_tenant(request: Request, body: dict[str, str]) -> dict[str, str]:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise UnauthenticatedError()
    tenant_id = body.get("tenant_id", "")
    if principal.kind != "platform_admin" and str(principal.tenant_id) != tenant_id:
        raise ForbiddenError("no membership in that tenant")
    # Multi-tenant switching is not yet supported for local sign-in; send back to the form.
    return {"redirect_url": "/login"}


@router.post("/api/v1/auth/step-up")
@expose(public=False, permission=None)
async def step_up(request: Request, body: dict[str, object] | None = None) -> dict[str, str]:
    """Re-confirm a sensitive action. Without an external IdP there is no MFA redirect: the
    person confirms and the session is stamped fresh. TOTP step-up is a later task (OQ-122)."""
    settings = request.app.state.settings
    payload = body or {}
    confirmed = str(payload.get("confirmed", "")).lower() in {"1", "true", "yes"}
    principal = getattr(request.state, "principal", None)
    if principal is None or not principal.session_id:
        raise UnauthenticatedError()
    if not confirmed:
        return {"stepped_up": "false"}
    data = await request.app.state.sessions.get(principal.session_id)
    if data is None:
        raise UnauthenticatedError()
    data.step_up_at = utcnow()
    await request.app.state.sessions.put(principal.session_id, data, settings.session_ttl_s)
    return {"stepped_up": "true"}


@router.get("/api/v1/.well-known/jwks.json")
@expose(public=True, permission=None)
async def jwks(request: Request) -> dict[str, object]:
    """Public JWKS. Empty until an internal signing key is configured."""
    raw = request.app.state.settings.internal_jwt_jwks
    if not raw:
        return {"keys": []}
    import orjson  # noqa: PLC0415

    loaded = orjson.loads(raw)
    if isinstance(loaded, dict):
        return loaded
    return {"keys": []}

"""Login, session, logout, switch-tenant and step-up.

Dev and single-tenant installs check a userid and password. Production uses the
customer's OIDC provider (authorization code in the browser, JWKS for bearers).
Spec: docs/03-specs/01-api-bff.md §3.
"""

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from ar_api.auth.complete import LoginError
from ar_api.auth.cookies import clear_session_cookies, write_session_cookies
from ar_api.auth.identity import login_otp_ok, resolve_oidc_claims, resolve_password_login
from ar_api.auth.lockout import lockout_subject
from ar_api.auth.mode import AuthMode, resolve_auth_mode
from ar_api.auth.oidc import OidcClient
from ar_api.auth.session import new_session, remember_profile
from ar_api.deps import expose
from ar_common.errors import (
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UnavailableError,
)
from ar_common.time import utcnow
from ar_common.web.problems import problem_response

if TYPE_CHECKING:
    from ar_api.auth.session import SessionData
    from ar_domain.db.context import Principal
    from ar_domain.identity.service import IdentityStore

router = APIRouter()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _issue_session(
    request: Request,
    result: dict[str, object],
    *,
    amr: list[str] | None = None,
    step_up: bool = False,
) -> tuple[str, SessionData]:
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
    data.amr = list(amr or [])
    if step_up:
        data.step_up_at = utcnow()
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


def _problem(request: Request, error: Exception) -> JSONResponse:
    from ar_common.errors import ArError  # noqa: PLC0415

    if not isinstance(error, ArError):
        error = UnauthenticatedError("invalid credentials")
    return problem_response(
        error,
        instance=request.url.path,
        request_id=str(getattr(request.state, "request_id", "")),
    )


def _login_error(request: Request, code: str) -> JSONResponse:
    if code == "tenant_suspended":
        from ar_common.errors import ArError  # noqa: PLC0415

        return _problem(request, ArError(ErrorCode.TENANT_SUSPENDED, "tenant is suspended"))
    if code == "mfa_required":
        return _problem(request, UnauthenticatedError("mfa required"))
    return _problem(request, UnauthenticatedError("invalid credentials"))


def _oidc(request: Request) -> OidcClient:
    return OidcClient(
        request.app.state.settings,
        request.app.state.oidc_states,
        http=getattr(request.app.state, "oidc_http", None),
        jwks=getattr(request.app.state, "oidc_jwks", None),
    )


async def _open_session(
    request: Request,
    result: dict[str, object],
    *,
    amr: list[str] | None = None,
    step_up: bool = False,
) -> tuple[str, str]:
    session_id, data = _issue_session(request, result, amr=amr, step_up=step_up)
    await request.app.state.sessions.put(
        session_id, data, int(request.app.state.settings.session_ttl_s)
    )
    return session_id, data.csrf_token


async def _finish_login(
    request: Request,
    result: dict[str, object],
    *,
    amr: list[str] | None = None,
    step_up: bool = False,
) -> JSONResponse:
    session_id, csrf = await _open_session(request, result, amr=amr, step_up=step_up)
    response = JSONResponse({"ok": True})
    write_session_cookies(response, request.app.state.settings, session_id, csrf)
    return response


@router.post("/api/v1/auth/login")
@expose(public=True, permission=None)
async def password_login(request: Request, body: dict[str, object] | None = None) -> JSONResponse:
    """Sign in with a userid and password. Production installs do not serve this."""
    if resolve_auth_mode(request.app.state.settings) is not AuthMode.PASSWORD:
        return _problem(request, ForbiddenError("password sign-in is not enabled"))
    return await _password_attempt(request, body or {})


async def _password_attempt(  # noqa: PLR0911
    request: Request, payload: dict[str, object]
) -> JSONResponse:
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    subject = lockout_subject(email or "missing")
    try:
        locked = await request.app.state.login_lockout.retry_after(subject)
    except UnavailableError as exc:
        return _problem(request, exc)
    if locked:
        return _problem(request, RateLimitedError("too many attempts", retry_after=locked))
    if not email or not password:
        return _login_error(request, "invalid_credentials")
    failure = ""
    result: dict[str, object] | None = None
    try:
        result = await resolve_password_login(request, email, password)
        if not await login_otp_ok(request, email, str(payload.get("otp") or "")):
            failure = "mfa_required"
    except LoginError as exc:
        failure = exc.code
    if failure or result is None:
        try:
            retry = await request.app.state.login_lockout.record_failure(subject)
        except UnavailableError as down:
            return _problem(request, down)
        if retry:
            return _problem(request, RateLimitedError("too many attempts", retry_after=retry))
        return _login_error(request, failure or "invalid_credentials")
    try:
        await request.app.state.login_lockout.clear(subject)
    except UnavailableError as exc:
        return _problem(request, exc)
    return await _finish_login(request, result)


@router.get("/api/v1/auth/oidc/start")
@expose(public=True, permission=None)
async def oidc_start(
    request: Request,
    purpose: Annotated[str, Query()] = "",
    next_path: Annotated[str, Query(alias="next")] = "/",
) -> Response:
    """Send the browser to the customer's identity provider."""
    if resolve_auth_mode(request.app.state.settings) is not AuthMode.OIDC:
        raise NotFoundError()
    try:
        url = await _oidc(request).authorization_url(
            purpose=purpose or "login", next_path=next_path
        )
    except LoginError as exc:
        return _problem(request, UnavailableError(exc.code))
    return RedirectResponse(url, status_code=302)


@router.get("/api/v1/auth/callback")
@expose(public=True, permission=None)
async def oidc_callback(request: Request, code: str = "", state: str = "") -> Response:
    """Exchange the authorization code and issue the browser session."""
    if resolve_auth_mode(request.app.state.settings) is not AuthMode.OIDC:
        raise NotFoundError()
    try:
        claims, stored = await _oidc(request).complete(code=code, state=state)
        result = await resolve_oidc_claims(request, claims)
    except LoginError as exc:
        if exc.code == "mfa_required":
            return RedirectResponse("/login?error=mfa", status_code=302)
        return _login_error(request, exc.code)
    amr = claims.get("amr")
    factors = [str(item) for item in amr] if isinstance(amr, list) else []
    step_up = stored.get("purpose") == "step-up"
    session_id, csrf = await _open_session(request, result, amr=factors, step_up=step_up)
    target = stored.get("next") or "/"
    redirect = RedirectResponse(target if target.startswith("/") else "/", status_code=302)
    write_session_cookies(redirect, request.app.state.settings, session_id, csrf)
    return redirect


@router.post("/api/v1/auth/logout")
@expose(public=False, permission=None)
async def logout(request: Request) -> JSONResponse:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None or principal.session_id is None:
        raise UnauthenticatedError()
    await request.app.state.sessions.delete(principal.session_id)
    # Sign-in is in-app, so logging out is just dropping the session and its cookies.
    response = JSONResponse({"ok": True})
    clear_session_cookies(response, request.app.state.settings)
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
    chat = request.app.state.chat
    engine = getattr(chat, "durable_engine", None)
    from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415

    if isinstance(chat, RepositoryReadModel):
        engine = await chat.engine_for()
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
    from ar_api.actors import chat_of  # noqa: PLC0415
    from ar_contracts.tenants import TenantSettings  # noqa: PLC0415
    from ar_domain.identity.tenant_settings import section, settings_for  # noqa: PLC0415

    defaults = TenantSettings()
    tenant_settings = settings_for(chat_of(request), principal.tenant_id)
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
    """Re-confirm a sensitive action.

    OIDC sends the browser back to the identity provider and stamps the session
    only when the token carries an MFA ``amr`` or ``acr``. Password mode stamps
    the session when the person confirms, and checks TOTP when that factor is on.
    """
    settings = request.app.state.settings
    payload = body or {}
    confirmed = str(payload.get("confirmed", "")).lower() in {"1", "true", "yes"}
    principal = getattr(request.state, "principal", None)
    if principal is None or not principal.session_id:
        raise UnauthenticatedError()
    if resolve_auth_mode(settings) is AuthMode.OIDC:
        return {"stepped_up": "false", "redirect_url": "/api/v1/auth/oidc/start?purpose=step-up"}
    if not confirmed:
        return {"stepped_up": "false"}
    if settings.password_mfa and not await login_otp_ok(
        request, str(getattr(principal, "email", "")), str(payload.get("otp") or "")
    ):
        raise UnauthenticatedError("mfa required")
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

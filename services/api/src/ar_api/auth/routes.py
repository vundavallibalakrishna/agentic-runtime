"""Login, callback, session, logout, switch-tenant and step-up.

Spec: docs/03-specs/01-api-bff.md §3.
"""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ar_api.auth.oidc import authorize_url, new_pkce, safe_return_to
from ar_api.auth.session import new_session
from ar_api.deps import expose
from ar_common.errors import ForbiddenError, NotFoundError, UnauthenticatedError
from ar_common.settings import EnvName

if TYPE_CHECKING:
    from ar_domain.db.context import Principal

router = APIRouter()


@router.get("/api/v1/auth/login")
@expose(public=True, permission=None)
async def login(
    request: Request, return_to: str = "/", tenant: str | None = None, idp: str | None = None
) -> RedirectResponse:
    """Start the OIDC authorization-code flow."""
    settings = request.app.state.settings
    verifier, challenge = new_pkce()
    state = uuid.uuid4().hex
    nonce = uuid.uuid4().hex
    request.app.state.login_states[state] = {
        "verifier": verifier,
        "nonce": nonce,
        "return_to": safe_return_to(return_to),
        "tenant": tenant,
    }
    target = authorize_url(
        issuer=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        redirect_uri=settings.public_url.rstrip("/") + "/api/v1/auth/callback",
        state=state,
        nonce=nonce,
        challenge=challenge,
        tenant=tenant,
        idp=idp,
    )
    return RedirectResponse(target, status_code=302)


@router.post("/api/v1/auth/dev-login")
@expose(public=True, permission=None)
async def dev_login(request: Request) -> RedirectResponse:
    """Sign in as the seeded admin. Disabled when ``AR_ENV=prod``."""
    settings = request.app.state.settings
    if settings.env is EnvName.PROD:
        raise NotFoundError()
    session_id, data = new_session(request.app.state.demo_tenant_id, request.app.state.demo_user_id)
    await request.app.state.sessions.put(session_id, data, int(settings.session_ttl_s))
    response = RedirectResponse("/chat", status_code=303)
    response.set_cookie("ar_session", session_id, httponly=True, samesite="lax", secure=False)
    response.set_cookie("ar_csrf", data.csrf_token, httponly=False, samesite="lax", secure=False)
    return response


@router.get("/api/v1/auth/callback")
@expose(public=True, permission=None)
async def callback(request: Request, code: str = "", state: str = "") -> RedirectResponse:
    """Finish login. Tests inject ``app.state.complete_login``."""
    saved = request.app.state.login_states.pop(state, None)
    if saved is None or not code:
        return RedirectResponse("/login?error=invalid_state", status_code=302)
    completer = request.app.state.complete_login
    try:
        result = await completer(code, saved)
    except Exception:  # noqa: BLE001 - login failures become a redirect
        return RedirectResponse("/login?error=tenant_not_found", status_code=302)
    if result.get("select_tenant"):
        return RedirectResponse("/select-tenant", status_code=302)
    session_id, data = new_session(uuid.UUID(result["tenant_id"]), uuid.UUID(result["user_id"]))
    data.access_token = str(result.get("access_token", ""))
    data.refresh_token = str(result.get("refresh_token", ""))
    await request.app.state.sessions.put(
        session_id, data, int(request.app.state.settings.session_ttl_s)
    )
    response = RedirectResponse(saved["return_to"], status_code=302)
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
    response = JSONResponse(
        {"logout_url": request.app.state.settings.oidc_issuer + "/protocol/openid-connect/logout"}
    )
    response.delete_cookie("ar_session")
    response.delete_cookie("ar_csrf")
    return response


@router.get("/api/v1/auth/session")
@expose(public=False, permission=None)
async def session(request: Request) -> dict[str, object]:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise UnauthenticatedError()
    return {
        "user": {
            "id": principal.id,
            "email": principal.email,
            "display_name": principal.display_name,
            "locale": "en-IN",
            "timezone": "Asia/Kolkata",
        },
        "tenant": {
            "id": None if principal.tenant_id is None else str(principal.tenant_id),
            "slug": "dev",
            "name": principal.display_name,
            "plan": "enterprise",
            "deployment_mode": request.app.state.settings.deployment_mode.value,
        },
        "permissions": sorted(principal.permissions),
        "roles": sorted(principal.roles),
        "memberships": [],
        "csrf_token": principal.csrf_token,
        "features": {},
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
    return {"redirect_url": f"/api/v1/auth/login?tenant={tenant_id}"}


@router.post("/api/v1/auth/step-up")
@expose(public=False, permission=None)
async def step_up(request: Request, body: dict[str, str] | None = None) -> dict[str, str]:
    settings = request.app.state.settings
    return_to = "/" if body is None else body.get("return_to", "/")
    return {
        "redirect_url": authorize_url(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            redirect_uri=settings.public_url.rstrip("/") + "/api/v1/auth/callback",
            state=uuid.uuid4().hex,
            nonce=uuid.uuid4().hex,
            challenge="step-up",
        )
        + "&acr_values=mfa&max_age=0&return_to="
        + safe_return_to(return_to)
    }


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

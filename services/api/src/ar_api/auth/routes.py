"""Login, callback, session, logout, switch-tenant and step-up.

Spec: docs/03-specs/01-api-bff.md §3.
"""

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ar_api.auth.complete import LoginError
from ar_api.auth.dev_users import DEV_TENANT_ID, catalogue
from ar_api.auth.oidc import authorize_url, new_pkce, safe_return_to
from ar_api.auth.session import new_session, remember_profile
from ar_api.deps import expose
from ar_common.errors import ForbiddenError, NotFoundError, UnauthenticatedError
from ar_common.settings import EnvName
from ar_common.time import utcnow

if TYPE_CHECKING:
    from ar_domain.db.context import Principal

router = APIRouter()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


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


async def _dev_email(request: Request) -> str:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        email = body.get("email") if isinstance(body, dict) else None
        if isinstance(email, str) and email.strip():
            return email.strip().lower()
    if "form" in content_type:
        form = await request.form()
        raw = form.get("email")
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()
    query = request.query_params.get("email", "").strip().lower()
    return query or "admin@dev.local"


@router.post("/api/v1/auth/dev-login")
@expose(public=True, permission=None)
async def dev_login(request: Request) -> RedirectResponse:
    """Sign in as one of the four seeded users. Disabled when ``AR_ENV=prod``."""
    settings = request.app.state.settings
    if settings.env is EnvName.PROD:
        raise NotFoundError()
    user = catalogue().get(await _dev_email(request))
    if user is None:
        return RedirectResponse("/login?error=unknown_user", status_code=303)
    from ar_domain.durable.bind import binding_from, user_for_email  # noqa: PLC0415

    binding = binding_from(request.app.state.chat)
    tenant_id = binding.tenant_id if binding is not None else DEV_TENANT_ID
    user_id = user_for_email(binding, user.email) or user.user_id
    session_id, data = new_session(tenant_id, user_id)
    remember_profile(
        data,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
        permissions=sorted(user.permissions),
    )
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
    except LoginError as exc:
        return RedirectResponse(f"/login?error={exc.code}", status_code=302)
    except Exception:  # noqa: BLE001 - login failures become a redirect
        return RedirectResponse("/login?error=tenant_not_found", status_code=302)
    if result.get("select_tenant"):
        return RedirectResponse("/select-tenant", status_code=302)
    session_id, data = new_session(
        uuid.UUID(str(result["tenant_id"])), uuid.UUID(str(result["user_id"]))
    )
    data.access_token = str(result.get("access_token", ""))
    data.refresh_token = str(result.get("refresh_token", ""))
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
            "name": "Dev",
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
async def step_up(request: Request, body: dict[str, object] | None = None) -> dict[str, str]:
    settings = request.app.state.settings
    payload = body or {}
    confirmed = str(payload.get("confirmed", "")).lower() in {"1", "true", "yes"}
    if confirmed and settings.env is not EnvName.PROD:
        principal = getattr(request.state, "principal", None)
        if principal is None or not principal.session_id:
            raise UnauthenticatedError()
        data = await request.app.state.sessions.get(principal.session_id)
        if data is None:
            raise UnauthenticatedError()
        data.step_up_at = utcnow()
        await request.app.state.sessions.put(principal.session_id, data, settings.session_ttl_s)
        return {"stepped_up": "true"}
    raw_return = "/" if body is None else body.get("return_to", "/")
    return_to = raw_return if isinstance(raw_return, str) else "/"
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

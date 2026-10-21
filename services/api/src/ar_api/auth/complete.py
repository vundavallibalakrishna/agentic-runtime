"""OIDC authorization-code completion. Spec: docs/03-specs/01-api-bff.md §3."""

from typing import TYPE_CHECKING

import httpx
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError

from ar_api.auth.dev_users import DEV_TENANT_ID, DevUser, catalogue

if TYPE_CHECKING:
    from ar_api.main import Settings

_JWT = JsonWebToken(["RS256", "RS384", "RS512", "ES256", "PS256"])


class LoginError(Exception):
    """A login failure the callback turns into ``/login?error=``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def organization_aliases(claims: dict[str, object]) -> list[str]:
    """Aliases from a Keycloak ``organization`` claim (object, list, or string)."""
    raw = claims.get("organization")
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    if isinstance(raw, dict):
        return [str(key) for key in raw if str(key).strip()]
    return []


def choose_organization(
    aliases: list[str],
    *,
    hint: str | None,
    email: str,
) -> str | None:
    """Pick one organization. ``None`` means the browser must choose."""
    if hint:
        if aliases and hint not in aliases:
            raise LoginError("tenant_not_found")
        return hint
    if len(aliases) > 1:
        return None
    if len(aliases) == 1:
        return aliases[0]
    domain = email.split("@", 1)[1] if "@" in email else ""
    if domain == "dev.local":
        return "dev"
    raise LoginError("tenant_not_found")


def profile_for(email: str, organization: str) -> DevUser:
    """Map a known seeded user. Other people in ``dev`` become members."""
    if organization != "dev":
        raise LoginError("tenant_not_found")
    known = catalogue().get(email.lower())
    if known is not None:
        return known
    from ar_domain.chat.service import demo_id  # noqa: PLC0415
    from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS  # noqa: PLC0415

    return DevUser(
        email=email.lower(),
        display_name=email.split("@", 1)[0],
        user_id=demo_id(email.lower()),
        roles=("member",),
        permissions=frozenset(SYSTEM_ROLE_PERMISSIONS["member"]),
    )


def login_result(user: DevUser, *, access_token: str, refresh_token: str) -> dict[str, object]:
    """Session fields the callback stores. Tokens stay out of logs."""
    return {
        "tenant_id": str(DEV_TENANT_ID),
        "user_id": str(user.user_id),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "email": user.email,
        "display_name": user.display_name,
        "roles": list(user.roles),
        "permissions": sorted(user.permissions),
    }


def _audience_ok(claims: dict[str, object], client_id: str) -> bool:
    audience = claims.get("aud")
    values = audience if isinstance(audience, list) else [audience]
    if client_id in values:
        return True
    # Keycloak sets ``azp`` to the client and ``aud`` to ``account``.
    return claims.get("azp") == client_id


def _validated_claims(
    id_token: str,
    *,
    jwks: dict[str, object],
    issuer: str,
    client_id: str,
    nonce: str,
) -> dict[str, object]:
    try:
        key = JsonWebKey.import_key_set(jwks)
        claims = _JWT.decode(id_token, key)
        claims.validate()
    except JoseError as exc:
        raise LoginError("invalid_state") from exc
    loaded = dict(claims)
    if str(loaded.get("iss", "")).rstrip("/") != issuer.rstrip("/"):
        raise LoginError("invalid_state")
    if not _audience_ok(loaded, client_id):
        raise LoginError("invalid_state")
    if str(loaded.get("nonce", "")) != nonce:
        raise LoginError("invalid_state")
    return loaded


async def complete_oidc_login(
    settings: Settings,
    code: str,
    saved: dict[str, object],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, object]:
    """Exchange the code, check the ID token, and resolve the dev tenant."""
    issuer = settings.oidc_issuer.rstrip("/")
    redirect_uri = settings.public_url.rstrip("/") + "/api/v1/auth/callback"
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret.get_secret_value(),
        "code_verifier": str(saved.get("verifier", "")),
    }
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=15)
    try:
        token_response = await http.post(
            issuer + "/protocol/openid-connect/token",
            data=form,
            headers={"accept": "application/json"},
        )
        if token_response.status_code != 200:
            raise LoginError("tenant_not_found")
        body = token_response.json()
        if not isinstance(body, dict) or not isinstance(body.get("id_token"), str):
            raise LoginError("tenant_not_found")
        certs = await http.get(issuer + "/protocol/openid-connect/certs")
        if certs.status_code != 200:
            raise LoginError("tenant_not_found")
        jwks = certs.json()
        if not isinstance(jwks, dict):
            raise LoginError("tenant_not_found")
    except httpx.HTTPError as exc:
        raise LoginError("tenant_not_found") from exc
    finally:
        if owns_client:
            await http.aclose()
    claims = _validated_claims(
        str(body["id_token"]),
        jwks=jwks,
        issuer=issuer,
        client_id=settings.oidc_client_id,
        nonce=str(saved.get("nonce", "")),
    )
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if "@" not in email:
        raise LoginError("tenant_not_found")
    hint = saved.get("tenant")
    tenant_hint = hint if isinstance(hint, str) and hint else None
    organization = choose_organization(organization_aliases(claims), hint=tenant_hint, email=email)
    if organization is None:
        return {"select_tenant": "1"}
    user = profile_for(email, organization)
    return login_result(
        user,
        access_token=str(body.get("access_token", "")),
        refresh_token=str(body.get("refresh_token", "")),
    )

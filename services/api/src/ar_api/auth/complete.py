"""OIDC authorization-code completion. Spec: docs/03-specs/01-api-bff.md §3."""

from typing import TYPE_CHECKING

import httpx
from authlib.jose import JsonWebKey, JsonWebToken
from authlib.jose.errors import JoseError

from ar_common.logging import get_logger

logger = get_logger(__name__)

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
        aliases: list[str] = []
        for key, value in raw.items():
            nested = value.get("alias") if isinstance(value, dict) else None
            if isinstance(nested, str) and nested.strip():
                aliases.append(nested.strip())
            elif str(key).strip():
                aliases.append(str(key).strip())
        return aliases
    return []


def choose_organization(
    aliases: list[str],
    *,
    hint: str | None,
) -> str | None:
    """Pick the organization named by the token.

    ``None`` means the browser must choose between several. An empty string means the
    token names none, which a single-tenant install accepts: the tenant is then the one
    the process serves, and the person must still be one of its users.
    """
    if hint:
        if aliases and hint not in aliases:
            raise LoginError("tenant_not_found")
        return hint
    if len(aliases) > 1:
        return None
    if len(aliases) == 1:
        return aliases[0]
    return ""


def _token_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    error = str(body.get("error", ""))
    description = str(body.get("error_description", ""))
    return f"{error} {description}".strip()[:200]


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
    """Exchange the code and check the ID token. Return who signed in, not which tenant."""
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
            detail = _token_error(token_response)
            logger.warning(
                "oidc_token_exchange_failed",
                status=token_response.status_code,
                error=detail,
            )
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
        logger.warning("oidc_id_token_missing_email", claims=sorted(str(key) for key in claims))
        raise LoginError("tenant_not_found")
    hint = saved.get("tenant")
    tenant_hint = hint if isinstance(hint, str) and hint else None
    organization = choose_organization(organization_aliases(claims), hint=tenant_hint)
    if organization is None:
        return {"select_tenant": "1"}
    return {
        "email": email,
        "organization": organization,
        "display_name": str(claims.get("name") or ""),
        "access_token": str(body.get("access_token", "")),
        "refresh_token": str(body.get("refresh_token", "")),
    }

"""OIDC authorization-code sign-in and JWKS bearer checks.

The issuer, client id, and client secret are operator settings. They are never
written to a log, a trace, or a response. A bearer token is an access token
from that issuer, checked against its JWKS. It does not replace ``ark_`` keys.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx
import jwt
import orjson

from ar_api.auth.complete import LoginError

if TYPE_CHECKING:
    from ar_api.main import Settings

_SCOPES = "openid profile email"
_ALGS = ["RS256", "ES256"]


class MemoryOidcState:
    """Short-lived authorization-code state for one process."""

    def __init__(self) -> None:
        self._rows: dict[str, bytes] = {}

    async def put(self, state: str, payload: dict[str, str], ttl_s: int) -> None:
        del ttl_s
        self._rows[state] = orjson.dumps(payload)

    async def pop(self, state: str) -> dict[str, str] | None:
        raw = self._rows.pop(state, None)
        return _state(raw)


class ValkeyOidcState:
    """Authorization-code state shared by every API replica. ``ar:oidc:{state}``."""

    def __init__(self, url: str, *, client: object | None = None) -> None:
        self.url = url
        self._redis = client

    async def put(self, state: str, payload: dict[str, str], ttl_s: int) -> None:
        try:
            await self._client().set(
                _key(state), orjson.dumps(payload).decode(), ex=max(1, ttl_s)
            )
        except Exception as exc:
            raise LoginError("oidc_unavailable") from exc

    async def pop(self, state: str) -> dict[str, str] | None:
        name = _key(state)
        try:
            client = self._client()
            raw = await client.get(name)
            await client.delete(name)
        except Exception as exc:
            raise LoginError("oidc_unavailable") from exc
        if isinstance(raw, bytes):
            raw = raw.decode()
        if not isinstance(raw, str):
            return None
        return _state(raw.encode())

    def _client(self) -> Any:
        if self._redis is None:
            from ar_common.valkey import valkey_client  # noqa: PLC0415

            self._redis = valkey_client(self.url, socket_connect_timeout=1, socket_timeout=2)
        return self._redis


class OidcClient:
    """Authorization-code client for the configured issuer."""

    def __init__(
        self,
        settings: Settings,
        states: object,
        *,
        http: Any | None = None,
        jwks: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings
        self.states = states
        self._http = http
        self.jwks = jwks
        self.jwks_uri = ""
        self.discovery_document: dict[str, Any] | None = None

    async def authorization_url(self, *, purpose: str, next_path: str) -> str:
        """Store PKCE state and return the IdP redirect."""
        document = await self.discovery()
        endpoint = str(document.get("authorization_endpoint") or "")
        if not endpoint:
            raise LoginError("oidc_unavailable")
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        nonce = secrets.token_urlsafe(18)
        await self.states.put(  # type: ignore[attr-defined]
            state,
            {
                "verifier": verifier,
                "nonce": nonce,
                "purpose": purpose,
                "next": _local_path(next_path),
            },
            600,
        )
        query = {
            "response_type": "code",
            "client_id": self.settings.oidc_client_id,
            "redirect_uri": self.redirect_uri(),
            "scope": _SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        }
        if self.settings.oidc_require_mfa:
            acr = self.settings.oidc_mfa_acr.split(",")[0].strip() or "mfa"
            query["acr_values"] = acr
        return f"{endpoint}?{urlencode(query)}"

    async def complete(self, *, code: str, state: str) -> tuple[dict[str, Any], dict[str, str]]:
        """Exchange the code and return ``(claims, stored state)``."""
        stored = await self.states.pop(state)  # type: ignore[attr-defined]
        if not isinstance(stored, dict) or not stored.get("verifier"):
            raise LoginError("invalid_state")
        document = await self.discovery()
        token_endpoint = str(document.get("token_endpoint") or "")
        if not token_endpoint or not code:
            raise LoginError("oidc_unavailable")
        body = await self._post_form(
            token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri(),
                "client_id": self.settings.oidc_client_id,
                "client_secret": self.settings.oidc_client_secret.get_secret_value(),
                "code_verifier": stored["verifier"],
            },
        )
        id_token = str(body.get("id_token") or "")
        claims = self.verify(id_token, audience=self.settings.oidc_client_id)
        if claims is None or str(claims.get("nonce") or "") != stored.get("nonce"):
            raise LoginError("invalid_token")
        if not claims_have_mfa(claims, self.settings):
            raise LoginError("mfa_required")
        return claims, stored

    def verify(self, token: str, *, audience: str) -> dict[str, Any] | None:
        """Check a JWT against the configured issuer. A bad token is ``None``."""
        if not token or token.count(".") != 2:
            return None
        try:
            key = self._signing_key(token)
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key,
                algorithms=_ALGS,
                audience=audience,
                issuer=self.settings.oidc_issuer.rstrip("/"),
            )
        except Exception:  # noqa: BLE001 - a bad token is unauthenticated, not a crash
            return None
        return claims if isinstance(claims, dict) else None

    async def discovery(self) -> dict[str, Any]:
        if self.discovery_document is not None:
            return self.discovery_document
        issuer = self.settings.oidc_issuer.rstrip("/")
        if not issuer:
            raise LoginError("oidc_unavailable")
        document = await self._get_json(f"{issuer}/.well-known/openid-configuration")
        if str(document.get("issuer") or "").rstrip("/") != issuer:
            raise LoginError("oidc_unavailable")
        self.jwks_uri = str(document.get("jwks_uri") or "")
        self.discovery_document = document
        return document

    def redirect_uri(self) -> str:
        explicit = self.settings.oidc_redirect_url.strip()
        if explicit:
            return explicit
        return self.settings.public_url.rstrip("/") + "/api/v1/auth/callback"

    def _signing_key(self, token: str) -> Any:
        if isinstance(self.jwks, dict):
            return _key_from_jwks(token, self.jwks)
        url = self.settings.oidc_jwks_url.strip() or self.jwks_uri
        if not url:
            issuer = self.settings.oidc_issuer.rstrip("/")
            url = f"{issuer}/.well-known/jwks.json"
        return jwt.PyJWKClient(url).get_signing_key_from_jwt(token).key

    async def _get_json(self, url: str) -> dict[str, Any]:
        response = await self._request("GET", url, None)
        return _object(response)

    async def _post_form(self, url: str, form: dict[str, str]) -> dict[str, Any]:
        response = await self._request("POST", url, form)
        return _object(response)

    async def _request(self, method: str, url: str, form: dict[str, str] | None) -> Any:
        try:
            if self._http is not None:
                if method == "GET":
                    return await self._http.get(url)
                return await self._http.post(url, data=form)
            async with httpx.AsyncClient(timeout=5.0) as client:
                if method == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(url, data=form)
                response.raise_for_status()
                return response
        except LoginError:
            raise
        except Exception as exc:
            raise LoginError("oidc_unavailable") from exc


def claims_have_mfa(claims: dict[str, Any], settings: Settings) -> bool:
    """IdP-enforced MFA: ``amr`` or ``acr`` must name a configured factor."""
    if not settings.oidc_require_mfa:
        return True
    allowed_amr = _words(settings.oidc_mfa_amr)
    allowed_acr = _words(settings.oidc_mfa_acr)
    amr = claims.get("amr")
    if isinstance(amr, str):
        amr = [amr]
    if isinstance(amr, list) and allowed_amr.intersection(str(item) for item in amr):
        return True
    return str(claims.get("acr") or "") in allowed_acr


def _words(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _local_path(value: str) -> str:
    if value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def _key(state: str) -> str:
    return f"ar:oidc:{state}"


def _state(raw: bytes | None) -> dict[str, str] | None:
    if not raw:
        return None
    try:
        loaded = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    return {str(key): str(value) for key, value in loaded.items()}


def _object(response: Any) -> dict[str, Any]:
    status = getattr(response, "raise_for_status", None)
    if callable(status):
        status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise LoginError("oidc_unavailable")
    return payload


def _key_from_jwks(token: str, document: dict[str, Any]) -> Any:
    header = jwt.get_unverified_header(token)
    kid = str(header.get("kid") or "")
    keys = document.get("keys")
    if not isinstance(keys, list):
        return None
    chosen = None
    for item in keys:
        if isinstance(item, dict) and (not kid or str(item.get("kid") or "") == kid):
            chosen = item
            break
    if not isinstance(chosen, dict):
        return None
    return jwt.PyJWK.from_dict(chosen).key

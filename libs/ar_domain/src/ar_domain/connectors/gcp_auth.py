"""Google service-account JWT and the token exchange documented by Google.

The private key stays in the sealed connection secret. The minted bearer is
cached. A unit test checks the claim set from Google's service-account guide
and verifies the RS256 signature with the matching public key.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import orjson

from ar_domain.connectors.tokens import cached_token, remember_token
from ar_domain.tools.http_tools import guard_public

if TYPE_CHECKING:
    from collections.abc import Mapping

_OAUTH_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/cloud-platform.read-only"


def service_account_assertion(
    info: Mapping[str, object],
    scopes: tuple[str, ...],
    now: datetime,
) -> str:
    """Build the JWT Google documents for a service account."""
    from cryptography.hazmat.primitives import hashes, serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric import padding  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey  # noqa: PLC0415

    header: dict[str, str] = {"alg": "RS256", "typ": "JWT"}
    kid = info.get("private_key_id")
    if isinstance(kid, str) and kid:
        header["kid"] = kid
    issued = int(now.timestamp())
    claims = {
        "iss": str(info.get("client_email") or ""),
        "scope": " ".join(scopes),
        "aud": _OAUTH_URL,
        "iat": issued,
        "exp": issued + 3600,
    }
    signing = _b64(orjson.dumps(header)) + b"." + _b64(orjson.dumps(claims))
    key = serialization.load_pem_private_key(str(info.get("private_key") or "").encode(), None)
    if not isinstance(key, RSAPrivateKey):
        raise TypeError("service account key must be RSA")
    signature = key.sign(signing, padding.PKCS1v15(), hashes.SHA256())
    return (signing + b"." + _b64(signature)).decode()


def token_form(assertion: str) -> dict[str, str]:
    """The form body from Google's service-account guide."""
    return {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }


def bearer_for(  # noqa: PLR0911
    store: Any, row: dict[str, object], secret: str
) -> dict[str, object]:
    """Return a cached or newly exchanged bearer. The key is not in the result."""
    cached = cached_token(store, row)
    if cached and not cached.startswith("{"):
        return {"token": cached}
    try:
        info = orjson.loads(secret)
    except orjson.JSONDecodeError:
        return _fail("The secret must be a Google service-account JSON key.")
    if not isinstance(info, dict) or not info.get("private_key") or not info.get("client_email"):
        return _fail("The service-account JSON is missing client_email or private_key.")
    scopes = row.get("scopes")
    chosen = (
        tuple(str(item) for item in scopes) if isinstance(scopes, list) and scopes else (_SCOPE,)
    )
    try:
        assertion = service_account_assertion(info, chosen, datetime.now(UTC))
    except ValueError, TypeError:
        return _fail("The service-account private key could not be read.")
    problem = guard_public(_OAUTH_URL, allow=["*"], loopback=False)
    if problem:
        return _fail(problem)
    status, payload = _exchange(store, token_form(assertion))
    if status >= 400 or not isinstance(payload, dict) or not payload.get("access_token"):
        return _fail("Google did not return an access token. Check the service-account key.")
    token = str(payload["access_token"])
    raw_expires = str(payload.get("expires_in") or "")
    remember_token(store, row, token, int(raw_expires) if raw_expires.isdigit() else 3600)
    return {"token": token}


def _exchange(store: Any, form: dict[str, str]) -> tuple[int, object]:
    transport = getattr(store, "connector_transport", None)
    kwargs: dict[str, object] = {"timeout": 20.0, "follow_redirects": False}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as client:  # type: ignore[arg-type]
            response = client.post(_OAUTH_URL, data=form)
    except httpx.HTTPError:
        return 0, {}
    try:
        payload = orjson.loads(response.content)
    except orjson.JSONDecodeError:
        payload = {}
    return response.status_code, payload


def _b64(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _fail(text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": "credential_required"}

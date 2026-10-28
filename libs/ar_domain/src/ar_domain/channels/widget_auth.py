"""Host-signed widget JWTs. Spec: docs/03-specs/16-channels.md §7."""

import base64
import hashlib
import hmac
import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
import orjson
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from ar_common.errors import ForbiddenError
from ar_common.http import http_client
from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def allowed_origins(config: object) -> list[str]:
    """Only exact HTTP(S) origins may appear in frame-ancestors or postMessage."""
    if not isinstance(config, dict):
        return []
    raw = config.get("allowed_origins", config.get("allowedOrigins", []))
    if not isinstance(raw, list):
        return []
    found = []
    for value in raw:
        if not isinstance(value, str) or any(c.isspace() for c in value):
            continue
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError:
            continue
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in value
            or ";" in value
            or "\\" in value
            or parsed.scheme not in {"https", "http"}
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
            or (port is not None and not 0 < port <= 65535)
        ):
            continue
        found.append(value)
    return list(dict.fromkeys(found))


def _claims(  # noqa: PLR0911 - each malformed claim fails closed
    token: str, audience: str, algorithm: str
) -> tuple[dict[str, Any], bytes, bytes] | None:
    parts = token.split(".")
    if len(parts) != 3 or len(token) > 16384:
        return None
    try:
        header = orjson.loads(_b64(parts[0]))
        payload = orjson.loads(_b64(parts[1]))
        signature = _b64(parts[2])
    except ValueError:
        return None
    if not isinstance(header, dict) or header.get("alg") != algorithm or header.get("crit"):
        return None
    if not isinstance(payload, dict) or payload.get("aud") != audience:
        return None
    now = int(utcnow().timestamp())
    exp = payload.get("exp")
    if type(exp) is not int or not now < exp <= now + 600:
        return None
    if not isinstance(payload.get("sub"), str) or not payload["sub"].strip():
        return None
    for field in ("nbf", "iat"):
        value = payload.get(field)
        if value is not None and (type(value) is not int or value > now):
            return None
    return payload, f"{parts[0]}.{parts[1]}".encode(), signature


def verify_widget_token(token: str, secret: str, audience: str) -> dict[str, Any] | None:
    """Validate HS256, the integration audience and a maximum ten-minute lifetime."""
    parsed = _claims(token, audience, "HS256")
    if not secret or parsed is None:
        return None
    payload, signing, signature = parsed
    expected = hmac.new(secret.encode(), signing, hashlib.sha256).digest()
    return payload if hmac.compare_digest(expected, signature) else None


def verify_rsa_widget_token(token: str, jwks: object, audience: str) -> dict[str, Any] | None:
    """Accept only the registered RSA signing key, never a key supplied in the token."""
    parsed = _claims(token, audience, "RS256")
    if parsed is None or not isinstance(jwks, dict):
        return None
    header = orjson.loads(_b64(token.split(".", maxsplit=1)[0]))
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not isinstance(header.get("kid"), str):
        return None
    for key in keys:
        if not isinstance(key, dict) or key.get("kid") != header["kid"] or key.get("kty") != "RSA":
            continue
        if key.get("use", "sig") != "sig" or key.get("alg", "RS256") != "RS256":
            continue
        try:
            public = rsa.RSAPublicNumbers(
                int.from_bytes(_b64(str(key["e"]))), int.from_bytes(_b64(str(key["n"])))
            ).public_key()
            if public.key_size < 2048:
                return None
            public.verify(parsed[2], parsed[1], padding.PKCS1v15(), hashes.SHA256())
        except KeyError, ValueError, InvalidSignature:
            return None
        return parsed[0]
    return None


async def verify_registered_token(
    token: str, *, secret: str, audience: str, config: dict[str, object]
) -> dict[str, Any] | None:
    """Fetch only the administrator-registered HTTPS JWKS, with SSRF protection."""
    url = config.get("jwks_url", config.get("jwksUrl"))
    if not url:
        return verify_widget_token(token, secret, audience)
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    client = http_client()
    try:
        response = await client.request("GET", url, timeout=5)
        if response.status_code != 200 or len(response.content) > 65536:
            return None
        return verify_rsa_widget_token(token, response.json(), audience)
    except httpx.HTTPError, ForbiddenError, ValueError:
        return None
    finally:
        await client.aclose()


def sign_widget_token(*, secret: str, audience: str, email: str, name: str, exp: int) -> str:
    """Test and host helper. The product does not mint widget tokens."""
    header = _b64encode(orjson.dumps({"alg": "HS256", "typ": "JWT"}))
    body = _b64encode(orjson.dumps({"sub": email, "name": name, "aud": audience, "exp": exp}))
    signing = f"{header}.{body}".encode()
    signature = _b64encode(hmac.new(secret.encode(), signing, hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def widget_user(store: Any, tenant_id: uuid.UUID, email: str) -> uuid.UUID | None:
    """Memory-mode dev identities are confined to their seeded tenant."""
    from ar_domain.chat.service import demo_id  # noqa: PLC0415

    binding = getattr(store, "dev_binding", None)
    if binding is not None and binding.tenant_id == tenant_id:
        found = binding.users.get(email.lower())
        return found if isinstance(found, uuid.UUID) else None
    if tenant_id != demo_id("tenant"):
        return None
    key, _, domain = email.lower().partition("@")
    if domain == "dev.local" and key in {"admin", "builder", "member", "approver"}:
        return demo_id(key)
    return None


def _b64(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

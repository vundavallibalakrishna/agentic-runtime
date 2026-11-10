"""VAPID Web Push. The private key is the named secret ``web_push_vapid_private``.

A 404 or 410 from the push service drops that subscription. The body is not logged.
"""

from __future__ import annotations

import base64
import time
from typing import Any  # noqa: TC003 - httpx kwargs are built at runtime
from urllib.parse import urlparse

import httpx
import orjson
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ar_domain.tools.http_tools import guard_public

_TTL_S = 12 * 60 * 60


def load_private_key(pem: str) -> ec.EllipticCurvePrivateKey | None:
    """Return an ES256 key, or None when the secret is not one."""
    try:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
    except ValueError, TypeError:
        return None
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        return None
    return key


def public_key_b64(key: ec.EllipticCurvePrivateKey) -> str:
    raw = key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return _b64(raw)


def authorization_header(key: ec.EllipticCurvePrivateKey, endpoint: str) -> str:
    """RFC 8292 ``Authorization`` value for this push endpoint."""
    parsed = urlparse(endpoint)
    audience = f"{parsed.scheme}://{parsed.netloc}"
    token = _jwt(key, audience)
    return f"vapid t={token}, k={public_key_b64(key)}"


def post_push(
    endpoint: str,
    title: str,
    body: str,
    key: ec.EllipticCurvePrivateKey,
    *,
    transport: httpx.BaseTransport | None = None,
) -> int:
    """POST one notification. Returns the status, or 0 when the call is refused."""
    if transport is None:
        problem = guard_public(endpoint, allow=["*"], loopback=True)
        if problem:
            return 0
    headers = {
        "Authorization": authorization_header(key, endpoint),
        "Content-Type": "application/json",
        "TTL": "60",
    }
    payload = orjson.dumps({"title": title, "body": body})
    kwargs: dict[str, Any] = {"timeout": 10.0}
    if transport is not None:
        kwargs["transport"] = transport
    try:
        with httpx.Client(**kwargs) as client:
            response = client.post(endpoint, headers=headers, content=payload)
    except httpx.HTTPError:
        return 0
    return response.status_code


def _jwt(key: ec.EllipticCurvePrivateKey, audience: str) -> str:
    header = _b64(orjson.dumps({"typ": "JWT", "alg": "ES256"}))
    payload = _b64(
        orjson.dumps(
            {"aud": audience, "exp": int(time.time()) + _TTL_S, "sub": "mailto:noreply@dev.local"}
        )
    )
    signing = f"{header}.{payload}".encode()
    der = key.sign(signing, ec.ECDSA(hashes.SHA256()))
    raw_r, raw_s = decode_dss_signature(der)
    signature = _b64(raw_r.to_bytes(32, "big") + raw_s.to_bytes(32, "big"))
    return f"{header}.{payload}.{signature}"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

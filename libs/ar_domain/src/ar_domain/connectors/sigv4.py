"""AWS Signature Version 4 for connector calls.

The secret key is an input to HMAC. It is never placed in the URL, the
result, or a log line. The published IAM ListUsers example (30 Aug 2015)
is the vector the unit test locks.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping

_EMPTY = hashlib.sha256(b"").hexdigest()


def sign_headers(
    method: str,
    url: str,
    *,
    access_key: str,
    secret_key: str,
    region: str,
    service: str,
    now: datetime | None = None,
    body: bytes = b"",
    extra: Mapping[str, str] | None = None,
    session_token: str = "",
    content_hash: bool = True,
) -> dict[str, str]:
    """Return the headers a signed request must send, including Authorization."""
    stamp = now or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    amz_date = stamp.strftime("%Y%m%dT%H%M%SZ")
    day = amz_date[:8]
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port and parts.port not in {80, 443}:
        host = f"{host}:{parts.port}"
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"host": host, "x-amz-date": amz_date}
    if content_hash:
        headers["x-amz-content-sha256"] = payload_hash
    if session_token:
        headers["x-amz-security-token"] = session_token
    for key, value in (extra or {}).items():
        headers[key.lower()] = " ".join(str(value).strip().split())
    signed = tuple(sorted(headers))
    canonical_headers = "".join(f"{key}:{headers[key]}\n" for key in signed)
    canonical = "\n".join(
        (
            method.upper(),
            _uri(parts.path or "/"),
            _query(parts.query),
            canonical_headers,
            ";".join(signed),
            payload_hash,
        )
    )
    scope = f"{day}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        (
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical.encode()).hexdigest(),
        )
    )
    signature = hmac.new(
        _signing_key(secret_key, day, region, service),
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()
    signed_names = ";".join(signed)
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_names}, Signature={signature}"
    )
    return headers


def signature_of(headers: Mapping[str, str]) -> str:
    auth = headers.get("authorization") or ""
    marker = "Signature="
    start = auth.find(marker)
    if start < 0:
        return ""
    return auth[start + len(marker) :]


def _signing_key(secret: str, day: str, region: str, service: str) -> bytes:
    date_key = hmac.new(f"AWS4{secret}".encode(), day.encode(), hashlib.sha256).digest()
    region_key = hmac.new(date_key, region.encode(), hashlib.sha256).digest()
    service_key = hmac.new(region_key, service.encode(), hashlib.sha256).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()


def _uri(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return "/".join(quote(segment, safe="-_.~") for segment in path.split("/"))


def _query(raw: str) -> str:
    if not raw:
        return ""
    pairs: list[tuple[str, str]] = []
    for part in raw.split("&"):
        if not part:
            continue
        name, _, value = part.partition("=")
        pairs.append((name, value))
    pairs.sort()
    return "&".join(
        f"{quote(name, safe='-_.~')}={quote(value, safe='-_.~')}" for name, value in pairs
    )


def empty_payload_hash() -> str:
    return _EMPTY

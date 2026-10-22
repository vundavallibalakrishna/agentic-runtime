"""Webhook HMAC. Spec 15 §5. The secret never leaves the create and rotate responses."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime

TOLERANCE_S = 300


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def new_token() -> str:
    return secrets.token_urlsafe(24)


def sign(secret: str, body: bytes, timestamp: int) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def header_for(secret: str, body: bytes, timestamp: int) -> str:
    return f"t={timestamp},v1={sign(secret, body, timestamp)}"


def verify(secret: str, body: bytes, header: str, *, now: int | None = None) -> bool:
    """Timing-safe check of ``t=<unix>,v1=<hex>`` within five minutes."""
    parsed = _parse(header)
    if parsed is None or not secret:
        return False
    timestamp, digest = parsed
    current = int(datetime.now(UTC).timestamp()) if now is None else now
    if abs(current - timestamp) > TOLERANCE_S:
        return False
    expected = sign(secret, body, timestamp)
    return hmac.compare_digest(expected, digest)


def idempotency_key(body: bytes, *, path_value: str, header: str) -> str:
    """Prefer the configured path, then the header, then the body hash."""
    if path_value:
        return path_value
    if header.strip():
        return header.strip()
    return hashlib.sha256(body).hexdigest()


def _parse(header: str) -> tuple[int, str] | None:
    fields: dict[str, str] = {}
    for part in header.split(","):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        fields[name.strip()] = value.strip()
    raw = fields.get("t", "")
    digest = fields.get("v1", "")
    if not raw.isdigit() or not digest:
        return None
    return int(raw), digest

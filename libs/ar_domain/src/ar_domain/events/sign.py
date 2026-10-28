"""Webhook signatures and delivery backoff. Spec: docs/03-specs/20-notifications-events.md §3."""

import hashlib
import hmac
import uuid

import orjson

from ar_common.json_api import camelize

BACKOFF_S: tuple[int, ...] = (10, 30, 60, 300, 900, 1800, 3600, 7200, 14400, 21600, 21600, 21600)


def sign_body(secret: str, body: bytes, timestamp: int) -> str:
    """Return ``t=<unix>,v1=<hex hmac>`` over ``timestamp + '.' + body``."""
    mac = hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode() + body, hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"


def next_backoff_s(attempts: int) -> int | None:
    """Seconds until the next try. ``None`` means the delivery is dead."""
    if attempts >= len(BACKOFF_S):
        return None
    return BACKOFF_S[attempts]


def public_json_bytes(value: object) -> bytes:
    """Encode a webhook or SSE payload with camelCase keys."""
    return orjson.dumps(camelize(value), default=_json_default)


def _json_default(value: object) -> str:
    # asyncpg UUIDs subclass uuid.UUID; orjson only accepts the exact builtin type.
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"Unsupported public JSON type: {type(value).__name__}")


def request_fingerprint(method: str, path: str, body: bytes) -> str:
    """SHA-256 of method, path and body for idempotency."""
    digest = hashlib.sha256()
    digest.update(method.upper().encode())
    digest.update(b"\n")
    digest.update(path.encode())
    digest.update(b"\n")
    digest.update(body)
    return digest.hexdigest()

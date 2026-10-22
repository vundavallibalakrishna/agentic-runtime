"""Signed account-link tokens. Spec: docs/03-specs/16-channels.md §5."""

import hashlib
import hmac
import os
from datetime import timedelta

import orjson

from ar_common.time import utcnow

_DEFAULT_TTL = 900


def link_ttl_s() -> int:
    raw = os.environ.get("AR_CHANNEL_LINK_TTL_S", "").strip()
    if not raw:
        return _DEFAULT_TTL
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_TTL


def _secret() -> bytes:
    raw = os.environ.get("AR_CURSOR_SECRET", "dev-cursor-secret")
    return raw.encode()


def issue_link_token(integration_id: str, external_user_id: str) -> str:
    """Return a token the profile page can redeem once."""
    payload = {
        "integration_id": integration_id,
        "external_user_id": external_user_id,
        "exp": (utcnow() + timedelta(seconds=link_ttl_s())).isoformat(),
    }
    body = orjson.dumps(payload)
    digest = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    return f"{body.hex()}.{digest}"


def read_link_token(token: str) -> dict[str, str] | None:  # noqa: PLR0911
    """Return the claims, or None when the token is expired or forged."""
    body_hex, dot, digest = token.partition(".")
    if not dot or not body_hex or not digest:
        return None
    try:
        body = bytes.fromhex(body_hex)
    except ValueError:
        return None
    expected = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, digest):
        return None
    loaded = orjson.loads(body)
    if not isinstance(loaded, dict):
        return None
    exp = str(loaded.get("exp") or "")
    if exp <= utcnow().isoformat():
        return None
    integration_id = str(loaded.get("integration_id") or "")
    external_user_id = str(loaded.get("external_user_id") or "")
    if not integration_id or not external_user_id:
        return None
    return {"integration_id": integration_id, "external_user_id": external_user_id}

"""Host-signed widget JWTs. Spec: docs/03-specs/16-channels.md §7."""

import base64
import hashlib
import hmac
import uuid
from typing import TYPE_CHECKING

import orjson

from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def verify_widget_token(token: str, secret: str, audience: str) -> dict[str, Any] | None:  # noqa: PLR0911
    """Return claims when the signature, audience and expiry hold."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    signing = f"{parts[0]}.{parts[1]}".encode()
    try:
        signature = _b64(parts[2])
        payload = orjson.loads(_b64(parts[1]))
    except ValueError, orjson.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    expected = hmac.new(secret.encode(), signing, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        return None
    if str(payload.get("aud") or "") != audience:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(utcnow().timestamp()):
        return None
    if not str(payload.get("sub") or ""):
        return None
    return payload


def sign_widget_token(*, secret: str, audience: str, email: str, name: str, exp: int) -> str:
    """Test and host helper. The product does not mint widget tokens."""
    header = _b64encode(orjson.dumps({"alg": "HS256", "typ": "JWT"}))
    body = _b64encode(orjson.dumps({"sub": email, "name": name, "aud": audience, "exp": exp}))
    signing = f"{header}.{body}".encode()
    signature = _b64encode(hmac.new(secret.encode(), signing, hashlib.sha256).digest())
    return f"{header}.{body}.{signature}"


def widget_user(store: Any, tenant_id: uuid.UUID, email: str) -> uuid.UUID | None:
    """Map a verified email to an active user. Anonymous visitors are refused (OQ-02)."""
    lowered = email.lower()
    emails = getattr(store, "user_emails", {})
    if isinstance(emails, dict):
        for user_id, value in emails.items():
            if str(value).lower() == lowered and isinstance(user_id, uuid.UUID):
                return user_id
    if lowered.endswith("@dev.local") and tenant_id == _demo_tenant():
        key = lowered.split("@", 1)[0]
        if key in {"admin", "builder", "member", "approver"}:
            from ar_domain.chat.service import demo_id  # noqa: PLC0415

            return demo_id(key)
    return None


def _demo_tenant() -> uuid.UUID:
    from ar_domain.chat.service import demo_id  # noqa: PLC0415

    return demo_id("tenant")


def _b64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

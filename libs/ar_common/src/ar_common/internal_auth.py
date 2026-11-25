"""Service-to-service auth for a single-node install.

Spec: docs/05-contracts/internal-apis.md §1. Connector ``internal_jwt`` stays on
``ar_common.internal_jwt``. Calls between our own processes use one shared secret
(``AR_INTERNAL_AUTH_SECRET``): each request carries ``X-AR-Internal: <unix>.<hmac>``
over ``{timestamp}.{METHOD}.{path}``. The squid helper can sign that with the
standard library. An empty secret fails closed.
"""

import hashlib
import hmac
import os
import time
from urllib.parse import urlsplit

from ar_common.errors import UnauthenticatedError

_SKEW_S = 60

# target service → caller service → scopes that caller's token must carry
ALLOWED_CALLERS: dict[str, dict[str, frozenset[str]]] = {
    "model-gateway": {
        "runtime-worker": frozenset({"models:invoke", "models:embed"}),
        "system-worker": frozenset({"models:invoke", "models:embed"}),
        "ingest-worker": frozenset({"models:invoke", "models:embed"}),
        "mcp-gateway": frozenset({"models:invoke", "models:embed"}),
        "api": frozenset({"models:invoke", "models:embed"}),
    },
    "mcp-gateway": {
        "runtime-worker": frozenset({"tools:call", "tools:list"}),
        "api": frozenset({"tools:call", "tools:list"}),
        "system-worker": frozenset({"tools:call", "tools:list"}),
    },
    "sandbox-manager": {
        "mcp-gateway": frozenset({"sandboxes:manage"}),
        "api": frozenset({"sandboxes:manage"}),
        "system-worker": frozenset({"sandboxes:manage"}),
        "squid": frozenset(),
    },
    "api": {
        "channels": frozenset({"api:internal"}),
        "opa": frozenset({"api:internal"}),
        "runtime-worker": frozenset({"api:internal"}),
        "system-worker": frozenset({"api:internal"}),
        "ingest-worker": frozenset({"api:internal"}),
        "model-gateway": frozenset({"api:internal"}),
        "mcp-gateway": frozenset({"api:internal"}),
        "sandbox-manager": frozenset({"api:internal"}),
    },
    "channels": {
        "mcp-gateway": frozenset({"channels:deliver"}),
        "system-worker": frozenset({"channels:deliver"}),
        "api": frozenset({"channels:deliver"}),
    },
}


def sign_request(secret: str, method: str, path: str, *, now: int | None = None) -> str:
    """HMAC for one internal call. ``path`` is the URL path, without the query."""
    stamp = int(time.time()) if now is None else int(now)
    message = f"{stamp}.{method.upper()}.{path}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"{stamp}.{digest}"


def internal_headers(secret: str, method: str, path: str) -> dict[str, str]:
    """The header a caller sends. Empty when this install has no secret."""
    if not secret:
        return {}
    return {"X-AR-Internal": sign_request(secret, method, path)}


def verify_request(secret: str, method: str, path: str, presented: str | None) -> None:
    """Reject a missing, stale, or forged internal call."""
    if not secret:
        raise UnauthenticatedError("internal auth is not configured")
    token = (presented or "").strip()
    stamp_text, separator, digest = token.partition(".")
    if not separator or not stamp_text.isdigit() or not digest:
        raise UnauthenticatedError("internal auth token is missing")
    stamp = int(stamp_text)
    if abs(int(time.time()) - stamp) > _SKEW_S:
        raise UnauthenticatedError("internal auth token has expired")
    expected = sign_request(secret, method, path, now=stamp)
    if not hmac.compare_digest(token, expected):
        raise UnauthenticatedError("internal auth token is invalid")


def headers_from_env(method: str, url: str) -> dict[str, str]:
    """Sign a call with ``AR_INTERNAL_AUTH_SECRET``. Empty when the install has none."""
    secret = os.environ.get("AR_INTERNAL_AUTH_SECRET", "")
    return internal_headers(secret, method, urlsplit(url).path)


def secret_value(settings: object) -> str:
    """The install secret, or an empty string when it is not set."""
    raw = getattr(settings, "internal_auth_secret", "")
    getter = getattr(raw, "get_secret_value", None)
    if callable(getter):
        return str(getter() or "")
    return str(raw or "")

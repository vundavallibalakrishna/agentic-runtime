"""CSRF comparison. Spec: docs/03-specs/01-api-bff.md §4."""

import hmac
from urllib.parse import urlparse


def csrf_ok(header: str | None, expected: str | None) -> bool:
    """Constant-time compare of the CSRF header and the session token."""
    if not header or not expected:
        return False
    return hmac.compare_digest(header, expected)


def origin_ok(origin: str | None, public_url: str) -> bool:
    """The ``Origin`` header, when present, must match ``AR_PUBLIC_URL``."""
    if origin is None or origin == "":
        return True
    return urlparse(origin).netloc == urlparse(public_url).netloc

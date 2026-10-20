"""API keys, SCIM tokens and invitation tokens.

Spec: docs/03-specs/02-identity-tenancy.md §3.4 and §3.8.
"""

import hashlib
import secrets


def sha256_hex(value: str) -> str:
    """Hex SHA-256 of a secret. Stored keys never keep the raw value."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """Return ``(full key, prefix, sha256 hex)``.

    The key is ``ark_`` + 12-character prefix + 43-character secret.
    """
    prefix = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    full = f"ark_{prefix}{secret}"
    return full, prefix, sha256_hex(full)


def new_scim_token() -> tuple[str, str, str]:
    """Return ``(full token, prefix, sha256 hex)`` for a SCIM bearer token."""
    prefix = "scim_" + secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    full = prefix + secret
    return full, prefix, sha256_hex(full)


def new_invitation_token() -> tuple[str, str]:
    """Return ``(raw token, sha256 hex)``."""
    raw = secrets.token_urlsafe(32)
    return raw, sha256_hex(raw)


def constant_time_equal(left: str, right: str) -> bool:
    """Compare two hex digests without short-circuiting on length."""
    return secrets.compare_digest(left, right)

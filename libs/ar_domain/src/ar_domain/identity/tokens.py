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


def new_split_api_key() -> tuple[str, str, str, str]:
    """Return ``(key id, secret, prefix, sha256 hex of the secret)``.

    A two-part credential: the key id ``ak_`` + 12-character prefix is safe to display
    and is returned on every read; the secret ``sk_`` + 43-character body is returned
    once at creation and only its hash is stored. Presented as
    ``Authorization: Bearer ak_<prefix>.sk_<secret>``.
    """
    prefix = secrets.token_hex(6)
    key_id = f"ak_{prefix}"
    secret = f"sk_{secrets.token_urlsafe(32)}"
    return key_id, secret, prefix, sha256_hex(secret)


def split_credential(token: str) -> tuple[str, str] | None:
    """Parse ``ak_<prefix>.sk_<secret>`` into ``(prefix, secret)``; ``None`` if malformed."""
    key_id, separator, secret = token.partition(".")
    if separator != "." or not key_id.startswith("ak_") or not secret.startswith("sk_"):
        return None
    prefix = key_id.removeprefix("ak_")
    if len(prefix) != 12:
        return None
    return prefix, secret


def rotate_split_secret() -> tuple[str, str]:
    """Return ``(secret, sha256 hex)`` for a rotated two-part key, keeping the same key id."""
    secret = f"sk_{secrets.token_urlsafe(32)}"
    return secret, sha256_hex(secret)


def rotate_legacy_secret(prefix: str) -> tuple[str, str]:
    """Return ``(full ark_ token, sha256 hex)`` for a rotated legacy key, keeping the prefix."""
    full = f"ark_{prefix}{secrets.token_urlsafe(32)}"
    return full, sha256_hex(full)


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

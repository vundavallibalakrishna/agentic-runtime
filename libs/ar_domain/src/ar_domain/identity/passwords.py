"""Local password hashing for in-app sign-in.

Sign-in is handled by the product itself (no external identity provider): a user's
password is stored only as an argon2id hash on ``users.password_hash`` and verified
here. This is distinct from ``tokens.py`` (which hashes API-key and SCIM secrets with
SHA-256): a password is a human secret, so it needs a slow, salted hash. The secret is
never logged and never returned by an API after it is set. Spec: docs/06-security/authn-authz.md.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

# Defaults follow argon2-cffi's recommended parameters; a tenant may not tune them, so
# there is no setting. Changing these only affects newly set passwords.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an argon2id hash (salt + parameters embedded) for ``password``."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """True when ``password`` matches ``password_hash``. False on any mismatch or bad hash.

    Never raises: a malformed stored hash or a wrong password both return False, so the
    caller always answers the same way and in roughly constant time.
    """
    if not password_hash or not password:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except Argon2Error:
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when ``password_hash`` was made with older parameters and should be re-hashed."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Argon2Error:
        return False

"""Self-service password reset. The token is mailed in a link. Only its hash is stored.

A reset is a row in ``password_resets`` and the new password is written to the user's
row, both through the identity store, so the request and its completion can be served
by different replicas and survive a restart.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from ar_common.errors import ArError, ErrorCode
from ar_common.ids import new_id
from ar_common.settings import get_settings
from ar_common.time import utcnow
from ar_domain.identity.passwords import hash_password
from ar_domain.identity.recovery_tables import PasswordReset

if TYPE_CHECKING:
    import uuid

    from ar_domain.identity.models import User
    from ar_domain.identity.service import IdentityStore

_NOT_VALID = "This reset link is not valid. Ask for a new one."


async def request_reset(identity: IdentityStore, email: str) -> str | None:
    """Open a reset for the person with this address and return its token to be mailed.

    None when nobody with a password has the address: the caller answers the same either
    way, so the reply does not say whether an address can sign in. Only the token's hash
    is stored, in ``password_resets``, so any replica can complete the reset.
    """
    user = await identity.get_user_by_email(email.strip().lower())
    if user is None or not user.password_hash or user.status != "active":
        return None
    token = secrets.token_urlsafe(32)
    identity.add(
        PasswordReset(
            id=new_id(),
            tenant_id=user.tenant_id,
            user_id=user.id,
            token_hash=_hash(token),
            expires_at=utcnow() + timedelta(minutes=get_settings().password_reset_ttl_minutes),
        )
    )
    return token


async def confirm_reset(identity: IdentityStore, token: str, password: str) -> User:
    """Set a new password when the token is unused and unexpired. The token works once."""
    shortest = get_settings().password_min_length
    if len(password) < shortest:
        raise ArError(
            ErrorCode.VALIDATION_FAILED, f"The password needs at least {shortest} characters."
        )
    row = await identity.password_reset_by_hash(_hash(token))
    if row is None or row.used_at is not None:
        raise ArError(ErrorCode.VALIDATION_FAILED, _NOT_VALID)
    if row.expires_at < utcnow():
        raise ArError(
            ErrorCode.VALIDATION_FAILED, "This reset link has expired. Ask for a new one."
        )
    user = await identity.get_user(row.user_id)
    if user is None or user.status != "active":
        raise ArError(ErrorCode.VALIDATION_FAILED, _NOT_VALID)
    user.password_hash = hash_password(password)
    user.password_set_at = utcnow()
    row.used_at = utcnow()
    await identity.audit_password_reset(user)
    return user


def reset_link(public_url: str, token: str) -> str:
    """The address a person opens to choose a new password."""
    return f"{public_url.rstrip('/')}/reset-password?token={token}"


def remember_person(
    store: Any,
    *,
    email: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    password_hash: str,
    tenant_name: str = "",
    display_name: str = "",
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
    user: object | None = None,
) -> None:
    """Register one local password the reset and tenant picker can see."""
    people = _people(store)
    people[str(user_id)] = {
        "email": email.strip().lower(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "password_hash": password_hash,
        "tenant_name": tenant_name or str(tenant_id),
        "display_name": display_name or email,
        "permissions": list(permissions or []),
        "roles": list(roles or []),
        "user": user,
    }


def people_for(store: Any, email: str) -> list[dict[str, object]]:
    needle = email.strip().lower()
    return [row for row in _people(store).values() if row.get("email") == needle]


def _people(store: Any) -> dict[str, dict[str, object]]:
    current = getattr(store, "local_people", None)
    if not isinstance(current, dict):
        current = {}
        store.local_people = current
    return current


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

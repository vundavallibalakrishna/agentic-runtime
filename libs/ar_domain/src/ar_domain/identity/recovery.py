"""Self-service password reset. The token is mailed. Only its hash is stored."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid

from ar_common.errors import ArError, ErrorCode
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.actions import AuditAction
from ar_domain.audit.memory import remember
from ar_domain.identity.passwords import hash_password

_HOURS = 2


def request_reset(store: Any, email: str) -> None:
    """Queue a reset when the address is known. Unknown addresses stay silent."""
    person = _person(store, email)
    if person is None:
        return
    token = secrets.token_urlsafe(32)
    row_id = new_id()
    _resets(store)[row_id] = {
        "id": row_id,
        "tenant_id": person["tenant_id"],
        "user_id": person["user_id"],
        "token_hash": _hash(token),
        "expires_at": utcnow() + timedelta(hours=_HOURS),
        "used_at": None,
        "created_at": utcnow(),
    }
    deliver(
        store,
        {
            "to": str(person["email"]),
            "subject": "Reset your password",
            "body": token,
        },
    )


def confirm_reset(store: Any, token: str, password: str) -> dict[str, object]:
    """Set a new password when the token is unused and unexpired."""
    if len(password) < 8:
        raise ArError(ErrorCode.VALIDATION_FAILED, "password is too short")
    digest = _hash(token)
    now = utcnow()
    for row in _resets(store).values():
        if row.get("token_hash") != digest or row.get("used_at") is not None:
            continue
        expires = row.get("expires_at")
        if isinstance(expires, datetime) and expires < now:
            raise ArError(ErrorCode.VALIDATION_FAILED, "reset token has expired")
        person = _person_by_id(store, row.get("user_id"))
        if person is None:
            raise ArError(ErrorCode.VALIDATION_FAILED, "reset token is not valid")
        person["password_hash"] = hash_password(password)
        account: Any = person.get("user")
        if account is not None:
            account.password_hash = person["password_hash"]
        row["used_at"] = now
        remember(
            store,
            tenant_id=person["tenant_id"],
            actor_id=person["user_id"],
            action=AuditAction.AUTH_PASSWORD_RESET.value,
            target_type="user",
            target_id=person["user_id"],
            detail={},
        )
        return {
            "user_id": str(person["user_id"]),
            "tenant_id": str(person["tenant_id"]),
        }
    raise ArError(ErrorCode.VALIDATION_FAILED, "reset token is not valid")


def deliver(store: Any, message: dict[str, str]) -> None:
    """Hand a message to the outbox and to a configured mailer. The body is not logged."""
    outbox = getattr(store, "outbox", None)
    if not isinstance(outbox, list):
        outbox = []
        store.outbox = outbox
    outbox.append(dict(message))
    mailer = getattr(store, "mailer", None)
    if callable(mailer):
        mailer(dict(message))


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


def _resets(store: Any) -> dict[object, dict[str, object]]:
    current = getattr(store, "password_resets", None)
    if not isinstance(current, dict):
        current = {}
        store.password_resets = current
    return current


def _person(store: Any, email: str) -> dict[str, object] | None:
    found = people_for(store, email)
    return found[0] if len(found) == 1 else (found[0] if found else None)


def _person_by_id(store: Any, user_id: object) -> dict[str, object] | None:
    return _people(store).get(str(user_id))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

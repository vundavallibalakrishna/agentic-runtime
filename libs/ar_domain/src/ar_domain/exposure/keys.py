"""Agent API keys. The raw secret is returned once and only its hash is stored."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import TYPE_CHECKING, Any

from ar_common.errors import ArError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.identity.tokens import constant_time_equal, sha256_hex

if TYPE_CHECKING:
    import uuid

_PREFIX_LEN = 12
_DUMMY = sha256_hex("ara_missing")


def new_agent_key() -> tuple[str, str, str]:
    """Return ``(full key, prefix, sha256 hex)``.

    The key is ``ara_`` plus a 12-character prefix plus the secret.
    """
    prefix = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    full = f"ara_{prefix}{secret}"
    return full, prefix, sha256_hex(full)


def request_fingerprint(
    text: str, attachment_ids: list[str], conversation_id: str, *, extra: str = ""
) -> str:
    """Stable hash of the work a message send will do. The stream flag is not part of it."""
    body = f"{conversation_id}\n{text}\n{'|'.join(attachment_ids)}"
    if extra:
        body = f"{body}\n{extra}"
    return hashlib.sha256(body.encode()).hexdigest()


def _book(store: Any, name: str) -> dict[Any, Any]:
    current = getattr(store, name, None)
    if not isinstance(current, dict):
        current = {}
        setattr(store, name, current)
    return current


def _hits(store: Any) -> dict[str, list[float]]:
    current = getattr(store, "agent_rate_hits", None)
    if not isinstance(current, dict):
        current = {}
        store.agent_rate_hits = current
    return current


def public_key(row: dict[str, Any]) -> dict[str, Any]:
    """Key metadata. The hash and the secret are not included."""
    last = row.get("last_used_at")
    revoked = row.get("revoked_at")
    created = row.get("created_at")
    return {
        "id": str(row.get("id")),
        "agent_id": str(row.get("agent_id")),
        "label": str(row.get("label") or ""),
        "prefix": str(row.get("prefix") or ""),
        "scope": str(row.get("scope") or "agent"),
        "rate_limit_rpm": int(row.get("rate_limit_rpm") or 0),
        "monthly_quota": int(row.get("monthly_quota") or 0),
        "month_stamp": str(row.get("month_stamp") or ""),
        "month_count": int(row.get("month_count") or 0),
        "last_used_at": None if last is None else _iso(last),
        "revoked_at": None if revoked is None else _iso(revoked),
        "created_at": None if created is None else _iso(created),
    }


def _iso(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def audit_key(
    store: Any,
    *,
    tenant_id: uuid.UUID | None,
    actor_id: object,
    action: str,
    key_id: object,
    label: str,
    outcome: str = "success",
    extra: dict[str, object] | None = None,
) -> None:
    """Record an external key event. The detail carries the label, not the secret."""
    detail: dict[str, object] = {"label": label}
    if extra:
        detail.update(extra)
    remember(
        store,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        target_type="agent_api_key",
        target_id=key_id,
        detail=detail,
        outcome=outcome,
    )


def create_key(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    label: str,
    scope: str = "agent",
    rate_limit_rpm: int = 60,
    monthly_quota: int = 10000,
) -> tuple[dict[str, Any], str]:
    """Store a hash and return the raw key once."""
    clean = label.strip()
    if not clean or len(clean) > 80:
        raise ValidationFailedError("label is required")
    if scope not in {"agent", "workspace"}:
        raise ValidationFailedError("scope must be agent or workspace")
    if rate_limit_rpm < 1 or rate_limit_rpm > 6000:
        raise ValidationFailedError("rate limit is out of range")
    if monthly_quota < 0 or monthly_quota > 1_000_000:
        raise ValidationFailedError("monthly quota is out of range")
    full, prefix, digest = new_agent_key()
    now = utcnow()
    row = {
        "id": new_id(),
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "created_by_user_id": user_id,
        "label": clean,
        "prefix": prefix,
        "secret_hash": digest,
        "scope": scope,
        "rate_limit_rpm": rate_limit_rpm,
        "monthly_quota": monthly_quota,
        "month_stamp": now.strftime("%Y-%m"),
        "month_count": 0,
        "last_used_at": None,
        "revoked_at": None,
        "rotated_from_id": None,
        "created_at": now,
        "updated_at": now,
    }
    _book(store, "agent_api_keys")[row["id"]] = row
    audit_key(
        store,
        tenant_id=tenant_id,
        actor_id=user_id,
        action="agent_api_key.created",
        key_id=row["id"],
        label=clean,
        extra={"scope": scope, "agent_id": str(agent_id)},
    )
    return row, full


def list_keys(store: Any, tenant_id: uuid.UUID, agent_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = [
        row
        for row in _book(store, "agent_api_keys").values()
        if isinstance(row, dict)
        and row.get("tenant_id") == tenant_id
        and row.get("agent_id") == agent_id
    ]
    rows.sort(key=lambda item: str(item.get("created_at") or ""))
    return rows


def _owned(
    store: Any, tenant_id: uuid.UUID, agent_id: uuid.UUID, key_id: uuid.UUID
) -> dict[str, Any]:
    row = _book(store, "agent_api_keys").get(key_id)
    if (
        not isinstance(row, dict)
        or row.get("tenant_id") != tenant_id
        or row.get("agent_id") != agent_id
    ):
        raise NotFoundError("agent api key not found")
    return row


def revoke_key(
    store: Any, tenant_id: uuid.UUID, agent_id: uuid.UUID, key_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    row = _owned(store, tenant_id, agent_id, key_id)
    if row.get("revoked_at") is None:
        row["revoked_at"] = utcnow()
        row["updated_at"] = row["revoked_at"]
        audit_key(
            store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="agent_api_key.revoked",
            key_id=key_id,
            label=str(row.get("label") or ""),
        )
    return row


def rotate_key(
    store: Any, tenant_id: uuid.UUID, agent_id: uuid.UUID, key_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[dict[str, Any], str]:
    """Revoke the current key and return a new secret with the same limits."""
    previous = _owned(store, tenant_id, agent_id, key_id)
    if previous.get("revoked_at") is not None:
        raise ArError(ErrorCode.INVALID_STATE, "key is already revoked")
    created, secret = create_key(
        store,
        tenant_id=tenant_id,
        agent_id=agent_id,
        user_id=user_id,
        label=str(previous.get("label") or "key"),
        scope=str(previous.get("scope") or "agent"),
        rate_limit_rpm=int(previous.get("rate_limit_rpm") or 60),
        monthly_quota=int(previous.get("monthly_quota") or 0),
    )
    created["rotated_from_id"] = previous["id"]
    revoke_key(store, tenant_id, agent_id, key_id, user_id)
    audit_key(
        store,
        tenant_id=tenant_id,
        actor_id=user_id,
        action="agent_api_key.rotated",
        key_id=created["id"],
        label=str(created.get("label") or ""),
        extra={"previous_id": str(previous["id"])},
    )
    return created, secret


def lookup(store: Any, token: str) -> tuple[dict[str, Any] | None, str]:
    """Return the key row and a reason: ok, missing or revoked."""
    if not token.startswith("ara_") or len(token) < 4 + _PREFIX_LEN:
        _dummy_compare()
        return None, "missing"
    prefix = token[4 : 4 + _PREFIX_LEN]
    found: dict[str, Any] | None = None
    for row in _book(store, "agent_api_keys").values():
        if isinstance(row, dict) and row.get("prefix") == prefix:
            found = row
            break
    if found is None:
        _dummy_compare()
        return None, "missing"
    if not constant_time_equal(sha256_hex(token), str(found.get("secret_hash") or "")):
        return None, "missing"
    if found.get("revoked_at") is not None:
        return found, "revoked"
    return found, "ok"


def _dummy_compare() -> None:
    constant_time_equal(sha256_hex("ara_missing"), _DUMMY)


def mark_used(row: dict[str, Any]) -> None:
    row["last_used_at"] = utcnow()
    row["updated_at"] = row["last_used_at"]


def take_rate(store: Any, row: dict[str, Any]) -> tuple[bool, int, int]:
    """One-minute window for this key. Returns allowed, limit and remaining."""
    limit = int(row.get("rate_limit_rpm") or 60)
    from ar_domain.process_state import take_window  # noqa: PLC0415

    shared = take_window(store, f"agent-api:{row.get('id')}", limit)
    if shared is not None:
        allowed, remaining = shared
        return allowed, limit, remaining
    now = time.monotonic()
    book = _hits(store)
    key = str(row.get("id"))
    current = [item for item in book.get(key, []) if now - item < 60]
    if len(current) >= limit:
        book[key] = current
        return False, limit, 0
    current.append(now)
    book[key] = current
    return True, limit, limit - len(current)


def take_quota(row: dict[str, Any]) -> bool:
    """Count one message against the monthly quota. Zero means no cap."""
    stamp = utcnow().strftime("%Y-%m")
    if row.get("month_stamp") != stamp:
        row["month_stamp"] = stamp
        row["month_count"] = 0
    limit = int(row.get("monthly_quota") or 0)
    count = int(row.get("month_count") or 0)
    if limit > 0 and count >= limit:
        return False
    row["month_count"] = count + 1
    row["updated_at"] = utcnow()
    return True

"""Shared guards for the records process store."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, NoReturn

from ar_common.errors import ForbiddenError, NotFoundError
from ar_common.time import utcnow
from ar_domain.audit.memory import remember

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def own(row: dict[str, object], tenant_id: uuid.UUID) -> bool:
    return row.get("tenant_id") == tenant_id


def require(actor: Actor, permission: str) -> None:
    if not actor.has(permission):
        raise ForbiddenError(f"missing permission {permission}")


def missing() -> NoReturn:
    raise NotFoundError()


def audit(  # noqa: PLR0917
    store: Any,
    actor: Actor,
    action: str,
    target_type: str,
    target_id: object,
    detail: dict[str, object],
    *,
    outcome: str = "success",
) -> int:
    remember(
        store,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        outcome=outcome,
    )
    event_id = len(store.audit_log)
    store.domain_events.append(
        {
            "topic": action,
            "payload": {
                "id": str(target_id),
                **{key: _jsonish(value) for key, value in detail.items()},
            },
            "at": utcnow().isoformat(),
        }
    )
    return event_id


def _jsonish(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def public(row: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in row.items():
        if key in {"blob", "envelope", "token"}:
            continue
        out[key] = _jsonish(value) if not isinstance(value, dict | list) else _walk(value)
    return out


def _walk(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _walk(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item) for item in value]
    return _jsonish(value)

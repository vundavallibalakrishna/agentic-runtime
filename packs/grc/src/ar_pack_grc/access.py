"""Shared guards for the GRC process store."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from ar_common.errors import ForbiddenError, NotFoundError
from ar_domain.records.access import audit, require
from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")
PACK_ID = "grc"


def snake_body(body: dict[str, Any]) -> dict[str, Any]:
    """Accept camelCase or snake_case keys on one object."""
    return {_CAMEL.sub("_", key).lower(): value for key, value in body.items()}


def rows(store: Any, name: str) -> dict[Any, dict[str, Any]]:
    return bucket(store, name)


def pack_enabled(store: Any, tenant_id: object) -> bool:
    """True when this tenant has the GRC pack switched on."""
    for flag in rows(store, "pack_flags").values():
        if str(flag.get("pack_id") or "") != PACK_ID:
            continue
        if flag.get("tenant_id") != tenant_id and str(flag.get("tenant_id")) != str(tenant_id):
            continue
        return bool(flag.get("enabled"))
    return False


def same_tenant(row: dict[str, Any], tenant_id: uuid.UUID) -> bool:
    return row.get("tenant_id") == tenant_id or str(row.get("tenant_id")) == str(tenant_id)


def require_enabled(store: Any, actor: Actor, *permissions: str) -> None:
    if not pack_enabled(store, actor.tenant_id):
        raise NotFoundError()
    for permission in permissions:
        require(actor, permission)


def one(store: Any, name: str, actor: Actor, item_id: uuid.UUID) -> dict[str, Any]:
    row = rows(store, name).get(item_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()
    return row


def owned(store: Any, name: str, actor: Actor) -> list[dict[str, Any]]:
    found = [row for row in rows(store, name).values() if same_tenant(row, actor.tenant_id)]
    found.sort(key=lambda row: str(row.get("key") or row.get("name") or row.get("title") or ""))
    return found


def record(
    store: Any, actor: Actor, action: str, target_id: object, detail: dict[str, Any]
) -> None:
    audit(store, actor, action, "grc", target_id, detail)


def parse_uuid(value: object, *, missing_ok: bool = False) -> uuid.UUID | None:
    if value is None or value == "":
        if missing_ok:
            return None
        raise NotFoundError()
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise NotFoundError() from exc


def forbid(detail: str) -> None:
    raise ForbiddenError(detail)


def present(row: dict[str, Any]) -> dict[str, Any]:
    """JSON-ready copy. Keys stay snake_case; the API rewrites them."""
    return {key: _jsonish(value) for key, value in row.items() if not str(key).startswith("_")}


def page(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": items, "next_cursor": None, "has_more": False}


def _jsonish(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonish(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonish(item) for item in value]
    return value

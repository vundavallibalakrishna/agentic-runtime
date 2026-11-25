"""Generic rows a pack stores for itself. No domain columns."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any


def dispatch_extensions(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    handler = {
        "put": _put,
        "get": _get,
        "list": _list,
        "compare": _compare,
    }.get(name)
    if handler is None:
        return _error("unknown_tool", f"unknown tool {name}")
    return handler(store, arguments)


def _put(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    pack_id = str(arguments.get("packId") or arguments.get("pack_id") or "").strip()
    bucket = str(arguments.get("bucket") or "").strip()
    payload = arguments.get("payload")
    if not pack_id or not bucket or not isinstance(payload, dict):
        return _error("validation_failed", "put needs packId, bucket and a payload object.")
    tenant_id = _uuid(arguments.get("_tenant_id"))
    if tenant_id is None:
        return _error("validation_failed", "put needs a tenant.")
    book = _book(store)
    row_id = _uuid(arguments.get("id")) or new_id()
    existing = book.get(row_id)
    version = 1
    if isinstance(existing, dict):
        if existing.get("tenant_id") != tenant_id or existing.get("pack_id") != pack_id:
            return _error("not_found", "No row with that id.")
        current = existing.get("version")
        version = (current if isinstance(current, int) else 1) + 1
    row: dict[str, object] = {
        "id": row_id,
        "tenant_id": tenant_id,
        "pack_id": pack_id,
        "bucket": bucket,
        "payload": payload,
        "version": version,
        "reason": str(arguments.get("reason") or ""),
        "updated_at": utcnow(),
    }
    book[row_id] = row
    from ar_domain.audit.memory import remember  # noqa: PLC0415

    remember(
        store,
        tenant_id=row.get("tenant_id"),
        actor_id=arguments.get("_user_id") or "tool",
        action="extensions.put",
        target_type="extension_row",
        target_id=row_id,
        detail={"version": version, "bucket": bucket, "reason": row["reason"]},
    )
    saved = _ok({"id": str(row_id), "version": version, "bucket": bucket})
    saved["text"] = f"saved {row_id}"
    return saved


def _get(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    row_id = _uuid(arguments.get("id"))
    row = _book(store).get(row_id) if row_id else None
    tenant_id = _uuid(arguments.get("_tenant_id"))
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        return _error("not_found", "No row with that id.")
    shown = _ok(_public(row))
    shown["text"] = str(row.get("payload"))
    return shown


def _list(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    pack_id = str(arguments.get("packId") or arguments.get("pack_id") or "")
    bucket = str(arguments.get("bucket") or "")
    tenant_id = _uuid(arguments.get("_tenant_id"))
    rows = [
        _public(row)
        for row in _book(store).values()
        if row.get("tenant_id") == tenant_id
        and (not pack_id or row.get("pack_id") == pack_id)
        and (not bucket or row.get("bucket") == bucket)
    ]
    return _ok({"rows": rows})


def _compare(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """Field deltas of two JSON objects, computed here, never by a model."""
    del store
    left = arguments.get("left")
    right = arguments.get("right")
    if not isinstance(left, dict) or not isinstance(right, dict):
        return _error("validation_failed", "compare needs left and right objects.")
    keys = sorted(set(left) | set(right))
    changes = [
        {"field": key, "left": left.get(key), "right": right.get(key)}
        for key in keys
        if left.get(key) != right.get(key)
    ]
    shown = _ok({"changes": changes, "unchanged": len(keys) - len(changes)})
    shown["text"] = str(changes)
    return shown


def _book(store: Any) -> dict[Any, dict[str, object]]:
    found = getattr(store, "extension_rows", None)
    if not isinstance(found, dict):
        found = {}
        store.extension_rows = found
    return found


def _public(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(row.get("id")),
        "packId": row.get("pack_id"),
        "bucket": row.get("bucket"),
        "payload": row.get("payload"),
        "version": row.get("version"),
        "reason": row.get("reason") or "",
    }


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except TypeError, ValueError:
        return None


def _ok(body: dict[str, object]) -> dict[str, object]:
    return {"text": "ok", "structured": body, "is_error": False}


def _error(code: str, message: str) -> dict[str, object]:
    return {
        "text": message,
        "structured": {"code": code},
        "is_error": True,
        "code": code,
    }

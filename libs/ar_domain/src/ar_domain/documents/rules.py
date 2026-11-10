"""Versioned rule sets. A published version is immutable tenant or pack content.

Core stores the statements a tenant supplied. It does not name a framework.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING, Any

import orjson

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def import_rule_set(store: Any, actor: Actor, payload: dict[str, object]) -> dict[str, object]:
    """Store one version. The same id, version, items and hash is a no-op."""
    set_id, version, items, sha, source = _parsed(payload, require_version=True)
    existing = find_version(store, actor.tenant_id, set_id, version)
    if existing is not None:
        if not _same(existing, items, sha):
            raise ConflictError("That rule-set version is already stored and cannot be changed.")
        return public_rule_set(existing)
    return _insert(
        store,
        actor,
        set_id=set_id,
        version=version,
        items=items,
        sha=sha,
        source=source,
    )


def export_rule_set(store: Any, actor: Actor, set_id: str, version: str = "") -> dict[str, object]:
    """The stored rule set. Another tenant's set is not found."""
    row = find_version(store, actor.tenant_id, set_id.strip(), version.strip())
    if row is None:
        raise NotFoundError()
    return public_rule_set(row)


def remember(
    store: Any,
    actor: Actor,
    payload: dict[str, object] | None,
    *,
    statements: list[str],
    rule_set_id: str,
) -> tuple[list[tuple[str, str]], str, str, uuid.UUID | None]:
    """Caller statements plus a rule set. A value that is not a rule set is ignored."""
    caller = [
        (f"s{index}", text.strip())
        for index, text in enumerate(statements, start=1)
        if text.strip()
    ]
    set_id = rule_set_id.strip()
    version = ""
    extra: list[tuple[str, str]] = []
    source: uuid.UUID | None = None
    if isinstance(payload, dict):
        set_id = str(payload.get("id") or set_id).strip()
        version = str(payload.get("version") or "")
        raw_items = payload.get("items")
        extra = _item_list(raw_items) if isinstance(raw_items, list) else []
        source = _as_uuid(payload.get("source_file_id") or payload.get("sourceFileId"))
        combined = [*caller, *extra]
        if set_id and combined:
            version = version or "1"
            sha = str(payload.get("sha256") or "").strip() or _sha(combined)
            saved = import_rule_set(
                store,
                actor,
                {
                    "id": set_id,
                    "version": version,
                    "items": [
                        {"item_id": item_id, "statement": text} for item_id, text in combined
                    ],
                    "source_file_id": source,
                    "sha256": sha,
                },
            )
            version = str(saved["version"])
            return combined, set_id, version, source
    if set_id:
        stored = find_version(store, actor.tenant_id, set_id, version)
        if stored is not None:
            extra = [
                (str(item.get("item_id") or ""), str(item.get("statement") or ""))
                for item in _rows(stored.get("items"))
            ]
            version = str(stored.get("version") or "")
            source = _as_uuid(stored.get("source_file_id"))
    return [*caller, *extra], set_id, version, source


def find_version(
    store: Any, tenant_id: uuid.UUID, set_id: str, version: str
) -> dict[str, object] | None:
    """One version, or the latest when ``version`` is empty. Ignores a broken value."""
    if not set_id:
        return None
    chosen: dict[str, object] | None = None
    for row in _bucket(store).values():
        if not isinstance(row, dict):
            continue
        if row.get("tenant_id") != tenant_id or row.get("set_id") != set_id:
            continue
        if version and row.get("version") != version:
            continue
        stamp = str(row.get("created_at") or "")
        if chosen is None or stamp >= str(chosen.get("created_at") or ""):
            chosen = row
    return chosen


def public_rule_set(row: dict[str, object]) -> dict[str, object]:
    source = row.get("source_file_id")
    return {
        "id": row.get("set_id"),
        "version": row.get("version"),
        "items": [
            {"item_id": item.get("item_id"), "statement": item.get("statement")}
            for item in _rows(row.get("items"))
        ],
        "source_file_id": None if source is None else str(source),
        "sha256": row.get("sha256") or "",
    }


def _insert(
    store: Any,
    actor: Actor,
    *,
    set_id: str,
    version: str,
    items: list[tuple[str, str]],
    sha: str,
    source: uuid.UUID | None,
) -> dict[str, object]:
    row_id = new_id()
    now = utcnow()
    row = {
        "id": row_id,
        "tenant_id": actor.tenant_id,
        "set_id": set_id,
        "version": version,
        "items": [{"item_id": item_id, "statement": text} for item_id, text in items],
        "source_file_id": source,
        "sha256": sha,
        "created_by": actor.user_id,
        "created_at": now,
    }
    _bucket(store)[row_id] = row
    log = getattr(store, "audit_log", None)
    if isinstance(log, list):
        log.append(
            {
                "tenant_id": str(actor.tenant_id),
                "actor_id": str(actor.user_id),
                "action": "rule_set.imported",
                "target_type": "rule_set",
                "target_id": str(row_id),
                "detail": {"rule_set_id": set_id, "version": version},
                "outcome": "success",
                "at": now.isoformat(),
            }
        )
    return public_rule_set(row)


def _parsed(
    payload: dict[str, object], *, require_version: bool
) -> tuple[str, str, list[tuple[str, str]], str, uuid.UUID | None]:
    set_id = str(payload.get("id") or "").strip()
    version = str(payload.get("version") or "").strip()
    if not set_id:
        raise ValidationFailedError("A rule set needs an id.")
    if require_version and not version:
        raise ValidationFailedError("A rule set needs a version.")
    items = _item_list(payload.get("items"))
    if not items:
        raise ValidationFailedError("A rule set needs at least one statement.")
    sha = str(payload.get("sha256") or "").strip() or _sha(items)
    source = _as_uuid(payload.get("source_file_id") or payload.get("sourceFileId"))
    return set_id, version, items, sha, source


def _item_list(raw: object) -> list[tuple[str, str]]:
    if not isinstance(raw, list):
        return []
    items: list[tuple[str, str]] = []
    for index, item in enumerate(raw, start=1):
        if isinstance(item, dict):
            text = str(item.get("statement") or "").strip()
            item_id = str(item.get("item_id") or item.get("itemId") or "").strip() or f"i{index}"
        else:
            text = str(item).strip()
            item_id = f"i{index}"
        if text:
            items.append((item_id, text))
    return items


def _same(row: dict[str, object], items: list[tuple[str, str]], sha: str) -> bool:
    stored = [
        (str(item.get("item_id") or ""), str(item.get("statement") or ""))
        for item in _rows(row.get("items"))
    ]
    return stored == items and str(row.get("sha256") or "") == sha


def _sha(items: list[tuple[str, str]]) -> str:
    payload = orjson.dumps([{"itemId": item_id, "statement": text} for item_id, text in items])
    return hashlib.sha256(payload).hexdigest()


def _bucket(store: Any) -> dict[object, object]:
    current = getattr(store, "rule_sets", None)
    if not isinstance(current, dict):
        current = {}
        store.rule_sets = current
    return current


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None

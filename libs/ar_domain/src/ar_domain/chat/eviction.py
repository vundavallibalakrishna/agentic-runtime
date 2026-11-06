"""Drop finished chat rows from the process cache once it passes a cap.

Conversation stubs stay so the list still has a title. Messages, runs and
events for those conversations reload from Postgres when it is bound. Active
runs are kept. A row that has not been flushed yet is kept too.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

from sqlalchemy import text

if TYPE_CHECKING:
    from typing import Any

_DEFAULTS = {
    "messages": 2000,
    "runs": 800,
    "events": 800,
    "blobs_bytes": 32 * 1024 * 1024,
}
_ACTIVE = {"queued", "running", "waiting_approval", "waiting_input"}


def evict_chat_cache(store: Any) -> dict[str, int]:
    """Trim the process cache. Returns how many entries left memory."""
    limits = _limits(store)
    removed = {"messages": 0, "runs": 0, "events": 0, "blobs": 0}
    protected = _protected(store)
    removed["messages"] = _trim_messages(store, protected, limits["messages"])
    removed["runs"] = _trim_runs(store, protected, limits["runs"])
    removed["events"] = _trim_events(store, protected, limits["events"])
    removed["blobs"] = _trim_blobs(store, limits["blobs_bytes"])
    return removed


def recall_conversation(store: Any, conversation_id: uuid.UUID) -> bool:
    """Load messages and runs for a conversation the cache has trimmed."""
    evicted = getattr(store, "evicted_conversations", None)
    if not isinstance(evicted, set) or conversation_id not in evicted:
        return False
    engine = getattr(store, "durable_engine", None)
    sync = getattr(engine, "sync_engine", None)
    if sync is None:
        return False
    try:
        with sync.connect() as connection:
            messages = _mappings(
                connection,
                "SELECT * FROM messages WHERE conversation_id = :id",
                {"id": conversation_id},
            )
            runs = _mappings(
                connection,
                "SELECT * FROM runs WHERE conversation_id = :id",
                {"id": conversation_id},
            )
    except Exception:  # noqa: BLE001 — opening the chat still works with what is cached
        return False
    from ar_domain.durable.hydrate import _merge, _text_of  # noqa: PLC0415

    for row in messages:
        row["text"] = _text_of(row.get("content"))
        _merge(store, "messages", row["id"], row)
    for row in runs:
        _merge(store, "runs", row["id"], row)
    evicted.discard(conversation_id)
    return bool(messages or runs)


def _limits(store: Any) -> dict[str, int]:
    override = getattr(store, "cache_limits", None)
    limits = dict(_DEFAULTS)
    if isinstance(override, dict):
        for key, value in override.items():
            allowed = isinstance(value, int) and not isinstance(value, bool) and value >= 0
            if key in limits and allowed:
                limits[key] = value
    return limits


def _protected(store: Any) -> set[object]:
    found: set[object] = set()
    runs = getattr(store, "runs", {})
    if isinstance(runs, dict):
        for run in runs.values():
            if isinstance(run, dict) and str(run.get("status")) in _ACTIVE:
                found.add(run.get("conversation_id"))
    conversations = getattr(store, "conversations", {})
    if isinstance(conversations, dict):
        for row in conversations.values():
            if isinstance(row, dict) and row.get("active_run_id") is not None:
                run_id = row.get("active_run_id")
                run = runs.get(run_id) if isinstance(runs, dict) else None
                if not isinstance(run, dict) or str(run.get("status")) in _ACTIVE:
                    found.add(row.get("id"))
    return found


def _trim_messages(store: Any, protected: set[object], limit: int) -> int:
    messages = getattr(store, "messages", None)
    if not isinstance(messages, dict):
        return 0
    removed = 0
    while len(messages) > limit:
        target = _oldest(store, protected, messages, "conversation_id")
        if target is None:
            break
        removed += _drop_matching(messages, "conversation_id", target)
        _mark(store, target)
    return removed


def _trim_runs(store: Any, protected: set[object], limit: int) -> int:
    runs = getattr(store, "runs", None)
    if not isinstance(runs, dict):
        return 0
    removed = 0
    while len(runs) > limit:
        target = _oldest(store, protected, runs, "conversation_id")
        if target is None:
            break
        removed += _drop_matching(runs, "conversation_id", target)
        _mark(store, target)
    return removed


def _trim_events(store: Any, protected: set[object], limit: int) -> int:
    events = getattr(store, "events", None)
    runs = getattr(store, "runs", None)
    if not isinstance(events, dict):
        return 0
    removed = 0
    while len(events) > limit:
        dropped = False
        for key in list(events):
            run = runs.get(key) if isinstance(runs, dict) else None
            conversation_id = run.get("conversation_id") if isinstance(run, dict) else None
            if conversation_id in protected or not _can_drop(events, key):
                continue
            _drop_key(events, key)
            removed += 1
            dropped = True
            if isinstance(conversation_id, uuid.UUID):
                _mark(store, conversation_id)
            break
        if not dropped:
            break
    return removed


def _trim_blobs(store: Any, limit: int) -> int:
    """Drop cached bytes, oldest first, until the cache fits. The object store has them."""
    blobs = getattr(store, "blobs", None)
    if not isinstance(blobs, dict):
        return 0
    removed = 0
    while _blob_bytes(blobs) > limit and blobs:
        blobs.pop(next(iter(blobs)), None)
        removed += 1
    return removed


def _oldest(
    store: Any, protected: set[object], bucket: dict[object, object], field: str
) -> object | None:
    conversations = getattr(store, "conversations", {})
    order = list(conversations) if isinstance(conversations, dict) else []
    seen: set[object] = set()
    for conversation_id in order:
        if conversation_id in protected or conversation_id in seen:
            continue
        if not any(
            isinstance(row, dict) and row.get(field) == conversation_id for row in bucket.values()
        ):
            continue
        if not any(
            isinstance(row, dict) and row.get(field) == conversation_id and _can_drop(bucket, key)
            for key, row in bucket.items()
        ):
            continue
        return cast("object", conversation_id)
    return None


def _drop_matching(bucket: dict[object, object], field: str, conversation_id: object) -> int:
    removed = 0
    for key, row in list(bucket.items()):
        if not isinstance(row, dict) or row.get(field) != conversation_id:
            continue
        if not _can_drop(bucket, key):
            continue
        _drop_key(bucket, key)
        removed += 1
    return removed


def _can_drop(bucket: dict[object, object], key: object) -> bool:
    dirty = getattr(bucket, "dirty", None)
    return not (isinstance(dirty, set) and key in dirty)


def _drop_key(bucket: dict[object, object], key: object) -> None:
    evict = getattr(bucket, "evict", None)
    if callable(evict):
        evict(key)
        return
    bucket.pop(key, None)


def _mark(store: Any, conversation_id: object) -> None:
    if not isinstance(conversation_id, uuid.UUID):
        return
    evicted = getattr(store, "evicted_conversations", None)
    if not isinstance(evicted, set):
        evicted = set()
        store.evicted_conversations = evicted
    evicted.add(conversation_id)


def _blob_bytes(blobs: dict[object, object]) -> int:
    total = 0
    for value in blobs.values():
        if isinstance(value, (bytes, bytearray, memoryview)):
            total += len(value)
    return total


def _mappings(connection: Any, sql: str, params: dict[str, object]) -> list[dict[str, Any]]:
    result = connection.execute(text(sql), params)
    return [dict(row) for row in result.mappings()]

"""Request-path state that more than one replica must see.

Standing approvals and review queues are durable rows in Postgres (the read
model hydrates and flushes them). Builder sessions, rate-limit buckets and the
external API minute window are Valkey keys. Staging and production refuse to
boot when any of these would stay inside the process.
"""

from __future__ import annotations

import contextlib
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import orjson

from ar_common.settings import get_settings, uses_shared_process_state

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings

_INDEX = "ar:builder-session:index"
_UUID_FIELDS = ("id", "tenant_id", "user_id", "conversation_id", "run_id")


class ProcessLocalStateRefusedError(RuntimeError):
    """Staging or production was asked to keep request-path state in memory."""


class ValkeyJsonBook(dict[Any, Any]):
    """A dict whose rows are JSON values in Valkey.

    ``__setitem__`` writes through. In-place edits of a row call ``persist``.
    A second process ``get`` reads the same key.
    """

    def __init__(self, client: Any, prefix: str = "ar:builder-session") -> None:
        super().__init__()
        self.client = client
        self.prefix = prefix

    def _redis_key(self, key: object) -> str:
        return f"{self.prefix}:{key}"

    def __setitem__(self, key: object, value: object) -> None:
        super().__setitem__(key, value)
        self.persist(key)

    def get(self, key: object, default: object = None) -> object:
        loaded = self._read(key)
        if loaded is not None:
            super().__setitem__(key, loaded)
            return loaded
        return super().get(key, default)

    def persist(self, key: object) -> None:
        if key not in self:
            return
        payload = _dump(self[key])
        redis_key = self._redis_key(key)
        self.client.set(redis_key, payload)
        self.client.sadd(_INDEX, redis_key)

    def _read(self, key: object) -> dict[str, object] | None:
        raw = self.client.get(self._redis_key(key))
        if not isinstance(raw, str) or not raw:
            return None
        loaded = _load(raw)
        return loaded if isinstance(loaded, dict) else None


def install_shared_state(store: object, settings: BaseServiceSettings) -> None:
    """Attach Valkey for the ephemeral books. Postgres covers the durable ones."""
    if not uses_shared_process_state(settings.env):
        return
    client = getattr(store, "valkey_client", None)
    if client is None:
        from ar_common.valkey import valkey_sync_client  # noqa: PLC0415

        client = valkey_sync_client(
            settings.valkey_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        try:
            client.ping()
        except Exception as exc:
            raise ProcessLocalStateRefusedError(
                "staging and production keep builder sessions, rate windows and the "
                "external API minute window in Valkey"
            ) from exc
        store.valkey_client = client  # type: ignore[attr-defined]
    store.builder_sessions = ValkeyJsonBook(client)  # type: ignore[attr-defined]
    require_shared_request_state(store, settings)


def bind_unit(model: object, unit: object) -> None:
    """Give one repository unit the process's shared Valkey books."""
    client = getattr(model, "valkey_client", None)
    if client is None:
        return
    unit.valkey_client = client  # type: ignore[attr-defined]
    unit.builder_sessions = ValkeyJsonBook(client)  # type: ignore[attr-defined]


def require_shared_request_state(store: object, settings: BaseServiceSettings) -> None:
    """Raise when staging or production would serve these books from memory."""
    if not uses_shared_process_state(settings.env):
        return
    if getattr(store, "valkey_client", None) is None:
        raise ProcessLocalStateRefusedError(
            "builder sessions, rate windows and the external API minute window are process-local"
        )
    book = getattr(store, "builder_sessions", None)
    if type(book) is dict:
        raise ProcessLocalStateRefusedError("builder sessions are process-local")


def remember_builder_session(store: object, session_id: object) -> None:
    """Write a builder session that was edited in place."""
    book = getattr(store, "builder_sessions", None)
    persist = getattr(book, "persist", None)
    if callable(persist):
        persist(session_id)


def take_window(store: object, key: str, limit: int) -> tuple[bool, int] | None:
    """Consume one hit from the shared window.

    ``None`` means this process is dev or CI and the caller keeps its own bucket.
    A Valkey error denies the hit. It does not fall back to process memory.
    """
    client = getattr(store, "valkey_client", None)
    if client is None:
        if uses_shared_process_state(get_settings().env):
            raise ProcessLocalStateRefusedError(
                "a rate window is process-local; staging and production use Valkey"
            )
        return None
    import time as time_mod  # noqa: PLC0415

    minute = int(time_mod.time() // 60)
    redis_key = f"ar:rate:{key}:{minute}"
    try:
        count = int(client.incr(redis_key))
        if count == 1:
            client.expire(redis_key, 70)
    except Exception:  # noqa: BLE001 - deny; do not open a private bucket
        return False, 0
    remaining = max(limit - count, 0)
    return count <= limit, remaining


def _dump(value: object) -> str:
    return orjson.dumps(value, default=_plain).decode()


def _plain(value: object) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _load(raw: str) -> object:
    data = orjson.loads(raw)
    if not isinstance(data, dict):
        return data
    for name in _UUID_FIELDS:
        item = data.get(name)
        if isinstance(item, str):
            try:
                data[name] = uuid.UUID(item)
            except ValueError:
                continue
    created = data.get("created_at")
    if isinstance(created, str):
        with contextlib.suppress(ValueError):
            data["created_at"] = datetime.fromisoformat(created)
    return data

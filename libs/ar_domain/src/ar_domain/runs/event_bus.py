"""Run-event bus. Every API replica reads the same Valkey stream.

The stream id is the cursor. A subscriber that connects after the event was
written still receives it, which a pub/sub channel would not do.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import orjson

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator

_MAXLEN = 10_000


class ValkeyRunBus:
    """``XADD`` / ``XREAD`` on ``ar:run:{id}``."""

    def __init__(self, url: str, *, client: object | None = None) -> None:
        self.url = url
        self._client = client
        self._pending: set[asyncio.Task[str]] = set()

    def publish(self, run_id: uuid.UUID, event: dict[str, object]) -> None:
        """Schedule a write. A caller with no running loop drops the publish."""
        payload = orjson.dumps(event).decode()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self.add(run_id, payload))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def add(self, run_id: uuid.UUID, payload: str) -> str:
        """Append one event and return the stream id."""
        client = self._redis()
        return str(
            await client.xadd(
                _key(run_id),
                {"payload": payload},
                maxlen=_MAXLEN,
                approximate=True,
            )
        )

    async def take(self, run_id: uuid.UUID, last: str) -> tuple[str, list[dict[str, object]]]:
        """Read the next batch after ``last``. An empty batch keeps ``last``."""
        client = self._redis()
        rows = await client.xread(
            {_key(run_id): last},
            count=32,
            block=1000,
        )
        events: list[dict[str, object]] = []
        cursor = last
        for _name, messages in rows or []:
            for message_id, fields in messages:
                cursor = str(message_id)
                event = _decode(fields)
                if event is not None:
                    events.append(event)
        return cursor, events

    async def listen(self, run_id: uuid.UUID) -> AsyncIterator[dict[str, object]]:
        """Yield events, including those written before this call subscribed."""
        last = "0-0"
        while True:
            last, events = await self.take(run_id, last)
            for event in events:
                yield event

    def _redis(self) -> Any:
        if self._client is None:
            from redis.asyncio import Redis  # noqa: PLC0415

            self._client = Redis.from_url(
                self.url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=2,
            )
        return self._client


def _key(run_id: uuid.UUID) -> str:
    return f"ar:run:{run_id}"


def _decode(fields: object) -> dict[str, object] | None:
    raw = fields.get("payload") if isinstance(fields, dict) else None
    if not isinstance(raw, str) or not raw:
        return None
    try:
        loaded = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None

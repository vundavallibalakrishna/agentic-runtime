"""The chat cache is trimmed in one pass, however much history the process holds.

A store loaded with a whole tenant's history is trimmed on every message. A trim that
scanned the bucket again for each conversation it dropped took hours with a few thousand
runs and stalled every eval batch on the worker.
"""

from __future__ import annotations

import time
import uuid
from types import SimpleNamespace

from ar_domain.chat.eviction import evict_chat_cache


class _Dirty(dict):  # type: ignore[type-arg]
    """A bucket that holds unsaved rows, as the durable store's buckets do."""

    def __init__(self) -> None:
        super().__init__()
        self.dirty: set[object] = set()


def _store(conversations: int) -> SimpleNamespace:
    store = SimpleNamespace(
        conversations={},
        messages=_Dirty(),
        runs=_Dirty(),
        events={},
        blobs={},
        cache_limits={"messages": 800, "runs": 800, "events": 800},
    )
    for _ in range(conversations):
        conversation_id = uuid.uuid4()
        run_id = uuid.uuid4()
        store.conversations[conversation_id] = {"id": conversation_id}
        store.runs[run_id] = {
            "id": run_id,
            "conversation_id": conversation_id,
            "status": "completed",
        }
        for _ in range(2):
            message_id = uuid.uuid4()
            store.messages[message_id] = {"id": message_id, "conversation_id": conversation_id}
        store.events[run_id] = [{"type": "run.completed"}]
    return store


def test_a_large_history_is_trimmed_quickly_and_oldest_first() -> None:
    store = _store(3000)
    order = list(store.conversations)
    started = time.perf_counter()
    removed = evict_chat_cache(store)
    assert time.perf_counter() - started < 2.0
    assert len(store.runs) == 800
    assert len(store.messages) == 800
    assert len(store.events) == 800
    assert removed["runs"] == 2200
    # The newest conversations keep their rows; the oldest are marked to reload.
    kept = {row["conversation_id"] for row in store.runs.values()}
    assert kept == set(order[-800:])
    assert set(order[:2200]) <= store.evicted_conversations


def test_active_and_unsaved_rows_stay() -> None:
    store = _store(1000)
    first, second = list(store.conversations)[:2]
    [live] = [key for key, row in store.runs.items() if row["conversation_id"] == first]
    store.runs[live]["status"] = "running"
    [unsaved] = [key for key, row in store.runs.items() if row["conversation_id"] == second]
    store.runs.dirty.add(unsaved)
    evict_chat_cache(store)
    assert live in store.runs
    assert live in store.events
    assert unsaved in store.runs
    assert first not in store.evicted_conversations

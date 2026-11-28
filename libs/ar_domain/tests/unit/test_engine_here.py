"""The store's database engine is only used on the loop it was bound on."""

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from ar_common.settings import get_settings, set_settings
from ar_domain.db import engine as engines
from ar_domain.db.engine import engine_here
from ar_domain.knowledge.syncutil import run_sync

if TYPE_CHECKING:
    import pytest

# No connection is opened: an engine connects on first use, and these tests never use one.
_URL = "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none"


async def _given(store: object) -> AsyncEngine | None:
    async with engine_here(store) as engine:
        return engine


def test_the_bound_loop_gets_the_shared_engine_and_another_loop_gets_its_own() -> None:
    async def scenario() -> None:
        shared = create_async_engine(_URL)
        store = SimpleNamespace(durable_engine=shared, durable_loop=asyncio.get_running_loop())

        assert await _given(store) is shared
        # A tool call runs its search like this: on a thread, on a loop of its own.
        other = run_sync(_given(store))
        assert isinstance(other, AsyncEngine)
        assert other is not shared
        assert isinstance(other.pool, NullPool)
        assert other.url == shared.url

    asyncio.run(scenario())


def test_a_store_without_a_database_gets_none() -> None:
    assert asyncio.run(_given(SimpleNamespace())) is None


def test_off_the_bound_loop_the_connection_waits_the_configured_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Under load a connection took longer than the two seconds this used to allow, and the
    # read failed the run with a bare TimeoutError.
    made: list[dict[str, Any]] = []

    def recording(url: str, **options: Any) -> AsyncEngine:
        made.append(options)
        return create_async_engine(url, **options)

    monkeypatch.setattr(engines, "create_async_engine", recording)
    before = get_settings()
    set_settings(before.model_copy(update={"database_connect_timeout_s": 7.5}))
    bound = asyncio.new_event_loop()
    try:
        store = SimpleNamespace(durable_engine=create_async_engine(_URL), durable_loop=bound)
        own = asyncio.run(_given(store))
    finally:
        set_settings(before)
        bound.close()
    assert own is not store.durable_engine
    assert made[-1]["connect_args"]["timeout"] == 7.5


def test_the_default_wait_is_longer_than_a_busy_moment() -> None:
    assert get_settings().database_connect_timeout_s >= 10

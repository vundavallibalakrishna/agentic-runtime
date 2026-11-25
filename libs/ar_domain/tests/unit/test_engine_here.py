"""The store's database engine is only used on the loop it was bound on."""

import asyncio
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from ar_domain.db.engine import engine_here
from ar_domain.knowledge.syncutil import run_sync

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

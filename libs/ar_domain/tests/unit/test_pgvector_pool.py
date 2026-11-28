"""Knowledge searches use the process's pooled engine on its loop. Proof: unit."""

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from ar_domain.knowledge import store_pgvector
from ar_domain.knowledge.store_pgvector import PgVectorStore

if TYPE_CHECKING:
    import pytest

DSN = "postgresql+asyncpg://reader:secret@db.example:5432/app"


def test_on_the_engines_own_loop_a_search_uses_the_shared_pool() -> None:
    async def session_bind() -> tuple[object, object]:
        shared = create_async_engine(DSN)
        store = PgVectorStore(dsn=DSN, engine=shared, loop=asyncio.get_running_loop())
        session = await store._connect(read=True)
        bind = session.bind
        await session.close()
        return bind, shared

    bind, shared = asyncio.run(session_bind())
    assert bind is shared


def test_on_another_loop_a_search_opens_one_connection_and_keeps_none() -> None:
    shared = create_async_engine(DSN)

    async def elsewhere() -> object:
        other_loop = asyncio.new_event_loop()
        store = PgVectorStore(dsn=DSN, engine=shared, loop=other_loop)
        session = await store._connect(read=True)
        bind = session.bind
        await session.close()
        other_loop.close()
        return bind

    bind = asyncio.run(elsewhere())
    assert bind is not shared
    assert isinstance(bind.pool, NullPool)  # type: ignore[attr-defined]


def test_without_a_shared_engine_the_store_keeps_no_pool() -> None:
    async def alone() -> object:
        session = await PgVectorStore(dsn=DSN)._connect(read=True)
        bind = session.bind
        await session.close()
        return bind

    assert isinstance(asyncio.run(alone()).pool, NullPool)  # type: ignore[attr-defined]


def test_the_connect_wait_is_a_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_VECTOR_PG_CONNECT_TIMEOUT_S", "7")
    assert store_pgvector._env_whole("AR_VECTOR_PG_CONNECT_TIMEOUT_S", 10) == 7
    monkeypatch.setenv("AR_VECTOR_PG_CONNECT_TIMEOUT_S", "soon")
    assert store_pgvector._env_whole("AR_VECTOR_PG_CONNECT_TIMEOUT_S", 10) == 10

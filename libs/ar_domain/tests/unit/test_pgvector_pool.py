"""Knowledge searches on one event loop share a connection pool. Proof: unit."""

import asyncio
from typing import TYPE_CHECKING

from ar_domain.knowledge import store_pgvector
from ar_domain.knowledge.store_pgvector import PgVectorStore, _loop_sessions

if TYPE_CHECKING:
    import pytest

DSN = "postgresql+asyncpg://reader:secret@db.example:5432/app"


def test_searches_on_one_loop_share_a_pool_and_each_loop_has_its_own() -> None:
    async def two_stores() -> tuple[object, object]:
        first = PgVectorStore(dsn=DSN)
        second = PgVectorStore(dsn=DSN)
        one = await first._connect(read=True)
        other = await second._connect(read=True)
        await one.close()
        await other.close()
        return one.bind, other.bind

    left = asyncio.run(two_stores())
    right = asyncio.run(two_stores())
    assert left[0] is left[1]
    assert right[0] is right[1]
    assert left[0] is not right[0]


def test_the_pool_is_sized_and_waits_as_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_VECTOR_PG_POOL_SIZE", "3")
    monkeypatch.setenv("AR_VECTOR_PG_CONNECT_TIMEOUT_S", "7")

    async def made() -> object:
        return _loop_sessions(DSN.replace("app", "other")).kw["bind"]

    engine = asyncio.run(made())
    pool = engine.pool  # type: ignore[attr-defined]
    assert pool.size() == 3
    assert engine.dialect.create_connect_args(engine.url)  # type: ignore[attr-defined]
    assert store_pgvector._env_whole("AR_VECTOR_PG_CONNECT_TIMEOUT_S", 10) == 7


def test_a_bad_setting_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_VECTOR_PG_POOL_SIZE", "many")
    assert store_pgvector._env_whole("AR_VECTOR_PG_POOL_SIZE", 5) == 5
    monkeypatch.setenv("AR_VECTOR_PG_POOL_SIZE", "0")
    assert store_pgvector._env_whole("AR_VECTOR_PG_POOL_SIZE", 5) == 5

"""A summary written on replica A is read on replica B. Proof: contract."""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.conversations.summary import read_summary
from ar_domain.identity.seed import apply
from ar_domain.readmodel.model import RepositoryReadModel
from ar_system.routines_store import bind_store
from ar_system.workflows.summary_refresh import refresh_conversation_summary

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def test_summary_written_on_replica_a_is_read_on_replica_b(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    connection = await engine.connect()
    try:
        found = (
            await connection.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).first()
    finally:
        await connection.close()
    assert found is not None
    tenant_id = found[0]
    first = RepositoryReadModel(database_url=database_url, allow_loopback=True)
    second = RepositoryReadModel(database_url=database_url, allow_loopback=True)
    async with first.open(tenant_id) as unit:
        user_id = next(iter(unit.display_names))
        agent = unit.ensure_assistant(tenant_id, user_id)
        conversation = unit.create_conversation(tenant_id, user_id, agent["id"])
        conversation_id = uuid.UUID(str(conversation["id"]))
        for _index in range(6):
            message_id = new_id()
            unit.messages[message_id] = {
                "id": message_id,
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "role": "user",
                "content": "The team agreed to keep the weekly note.",
                "text": "The team agreed to keep the weekly note.",
                "created_at": utcnow(),
            }
    bind_store(first)
    refreshed = await refresh_conversation_summary(
        {"tenant_id": str(tenant_id), "conversation_id": str(conversation_id)}
    )
    assert refreshed["summary"]
    async with second.open(tenant_id) as unit:
        seen = read_summary(unit, tenant_id, conversation_id)
    assert seen["summary"] == refreshed["summary"]
    assert seen["proof"] == "contract"
    check = await engine.connect()
    try:
        row = (
            await check.execute(
                text("SELECT summary FROM conversation_summaries WHERE conversation_id = :id"),
                {"id": conversation_id},
            )
        ).first()
    finally:
        await check.close()
        await engine.dispose()
    assert row is not None
    assert row[0] == refreshed["summary"]

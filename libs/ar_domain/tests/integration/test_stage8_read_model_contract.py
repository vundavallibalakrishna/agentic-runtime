"""Two repository units share Postgres. Proof label: contract (real Postgres, no model)."""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.identity.seed import apply
from ar_domain.readmodel.model import RepositoryReadModel

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


async def test_a_second_unit_reads_the_first_units_commit(database_url: str) -> None:
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
        created = unit.create_conversation(tenant_id, user_id, agent["id"])
        conversation_id = uuid.UUID(str(created["id"]))
    async with second.open(tenant_id) as unit:
        row = unit.conversations.get(conversation_id)
    assert isinstance(row, dict)
    assert row["tenant_id"] == tenant_id
    await engine.dispose()

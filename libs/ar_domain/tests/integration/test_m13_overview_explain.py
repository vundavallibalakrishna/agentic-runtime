"""Overview SQL can use the runs index."""

import os
import subprocess
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ar_domain.runs.service import OVERVIEW_SQL

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


async def test_runs_index_is_visible_to_explain(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        indexes = await connection.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'runs'")
        )
        names = {row[0] for row in indexes}
        assert "ix_runs_conversation" in names
        plan = await connection.execute(
            text("EXPLAIN " + OVERVIEW_SQL),
            {
                "tenant_id": "00000000-0000-0000-0000-000000000000",
                "start": datetime(2020, 1, 1, tzinfo=UTC),
                "end": datetime(2030, 1, 1, tzinfo=UTC),
            },
        )
        rendered = " ".join(row[0] for row in plan)
    await engine.dispose()
    assert "runs" in rendered

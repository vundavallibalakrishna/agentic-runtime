"""Alembic history is linear and reversible. Spec: docs/04-data/migrations.md."""

import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.engine.url import make_url

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


def _alembic(url: str, *args: str) -> str:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    completed = subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout


@pytest.fixture(scope="module")
def migrated(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url, "upgrade", "head")
    return url


def test_single_head_and_empty_check(migrated: str) -> None:
    heads = [line for line in _alembic(migrated, "heads").splitlines() if line.strip()]
    assert len(heads) == 1
    check = _alembic(migrated, "check")
    assert "No new upgrade operations detected" in check


def test_downgrade_and_upgrade(migrated: str) -> None:
    _alembic(migrated, "downgrade", "base")
    _alembic(migrated, "upgrade", "head")
    heads = [line for line in _alembic(migrated, "heads").splitlines() if line.strip()]
    assert len(heads) == 1


async def test_seed_is_idempotent(migrated: str) -> None:
    from ar_common.settings import BaseServiceSettings, set_settings
    from ar_domain.db.engine import get_engine
    from ar_domain.seed import apply

    os.environ["AR_DATABASE_URL"] = migrated
    os.environ["AR_PG_HOST_PORT"] = str(make_url(migrated).port or 5432)
    set_settings(BaseServiceSettings(_env_file=None))
    engine = get_engine(migrated)
    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("SELECT 1"))
    await apply()
    await apply()
    async with engine.connect() as connection:
        plans = await connection.scalar(text("SELECT count(*) FROM plans"))
        roles = await connection.scalar(
            text("SELECT count(*) FROM roles WHERE tenant_id IS NULL AND is_system")
        )
    assert plans is not None and plans >= 4
    assert roles == 7

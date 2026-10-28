"""Pack Alembic stays off the core history and enforces tenant RLS."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


def _alembic(url: str, config: str, *args: str) -> str:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    completed = subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", "-c", config, *args],  # noqa: S607
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed.stdout


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url, "libs/ar_domain/alembic.ini", "upgrade", "head")
    return url


async def test_pack_upgrade_downgrade_and_cross_tenant_rls(database_url: str) -> None:
    before = _alembic(database_url, "libs/ar_domain/alembic.ini", "heads")
    _alembic(database_url, "packs/grc/alembic.ini", "upgrade", "head")
    _alembic(database_url, "packs/grc/alembic.ini", "check")
    engine = create_async_engine(database_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    plan_id = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO plans (id, key, name) VALUES (:id, :key, 'GRC') "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {"id": plan_id, "key": f"grc-{plan_id.hex[:8]}"},
        )
        plan = await connection.scalar(text("SELECT id FROM plans LIMIT 1"))
        for tenant_id, slug in ((tenant_a, "grc-a-tenant"), (tenant_b, "grc-b-tenant")):
            await connection.execute(
                text(
                    "INSERT INTO tenants (id, slug, name, plan_id) "
                    "VALUES (:id, :slug, :name, :plan_id)"
                ),
                {"id": tenant_id, "slug": slug, "name": slug, "plan_id": plan},
            )
        await connection.execute(
            text(
                "INSERT INTO grc.controls (tenant_id, key, title) "
                "VALUES (:tenant_id, 'cc-probe', 'Probe')"
            ),
            {"tenant_id": tenant_a},
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_b)},
        )
        visible = await connection.scalar(text("SELECT count(*) FROM grc.controls"))
        await connection.execute(text("RESET ROLE"))
        await connection.execute(text("SELECT set_config('app.tenant_id', '', true)"))
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        closed = await connection.scalar(text("SELECT count(*) FROM grc.frameworks"))
    await engine.dispose()
    assert visible == 0
    assert closed == 0
    _alembic(database_url, "packs/grc/alembic.ini", "downgrade", "base")
    _alembic(database_url, "packs/grc/alembic.ini", "upgrade", "head")
    after = _alembic(database_url, "libs/ar_domain/alembic.ini", "heads")
    assert before.strip() == after.strip()
    assert "0001" not in after

"""Row-level security fails closed. Spec: docs/04-data/rls.md."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


def _alembic(url: str, *args: str) -> None:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", *args],  # noqa: S607
        check=True,
        env=env,
    )


_MISSING = """
SELECT c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
WHERE n.nspname = 'public'
  AND c.relkind = 'r'
  AND (
    NOT c.relrowsecurity
    OR NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid)
  )
ORDER BY c.relname
"""


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url, "upgrade", "head")
    return url


async def _missing(url: str) -> list[str]:
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        rows = await connection.execute(text(_MISSING))
        found = [str(row[0]) for row in rows]
    await engine.dispose()
    return found


async def test_rls_every_tenant_table_has_policy(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("CREATE TABLE rls_probe (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)")
        )
        rows = await connection.execute(text(_MISSING))
        found = [str(row[0]) for row in rows]
        await connection.execute(text("DROP TABLE rls_probe"))
    await engine.dispose()
    assert "rls_probe" in found
    assert await _missing(database_url) == []


async def test_rls_no_context_fails_closed(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        count = await connection.scalar(text("SELECT count(*) FROM users"))
    await engine.dispose()
    assert count == 0


async def test_rls_cross_tenant_read_returns_nothing(database_url: str) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    plan_id = uuid.uuid4()
    user_b = uuid.uuid4()
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO plans (id, key, name, limits) VALUES (:id, :key, 'Plan', '{}'::jsonb)"
            ),
            {"id": plan_id, "key": f"plan-{plan_id.hex[:8]}"},
        )
        await connection.execute(
            text(
                "INSERT INTO tenants (id, slug, name, plan_id) "
                "VALUES (:id, :slug, 'A', :plan), (:other, :other_slug, 'B', :plan)"
            ),
            {
                "id": tenant_a,
                "slug": f"a-{tenant_a.hex[:8]}",
                "other": tenant_b,
                "other_slug": f"b-{tenant_b.hex[:8]}",
                "plan": plan_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO users (id, tenant_id, idp_subject, email, display_name) "
                "VALUES (:id, :tenant, 'b@example.com', 'b@example.com', 'B')"
            ),
            {"id": user_b, "tenant": tenant_b},
        )
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(tenant_a)},
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        seen = await connection.scalar(text("SELECT count(*) FROM users"))
        updated = await connection.execute(
            text("UPDATE users SET display_name = 'stolen' WHERE id = :id"),
            {"id": user_b},
        )
        deleted = await connection.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": user_b},
        )
    await engine.dispose()
    assert seen == 0
    assert updated.rowcount == 0
    assert deleted.rowcount == 0


async def test_rls_insert_wrong_tenant_rejected(database_url: str) -> None:
    engine = create_async_engine(database_url)
    tenant_b = await _one_tenant(engine)
    async with engine.begin() as connection:
        other = uuid.uuid4()
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(other)},
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        with pytest.raises(Exception, match="row-level security"):
            await connection.execute(
                text(
                    "INSERT INTO users (id, tenant_id, idp_subject, email, display_name) "
                    "VALUES (:id, :tenant, 'x', 'x@example.com', 'X')"
                ),
                {"id": uuid.uuid4(), "tenant": tenant_b},
            )
    await engine.dispose()


async def test_audit_append_only(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO audit_events "
                "(tenant_seq, actor_type, actor_id, action, target_type, prev_hash, hash) "
                "VALUES (1, 'system', 'seed', 'platform.session_opened', 'session', :pad, :pad)"
            ),
            {"pad": "0" * 64},
        )
        with pytest.raises(Exception, match="append-only"):
            await connection.execute(text("UPDATE audit_events SET action = action"))
    await engine.dispose()


async def _one_tenant(engine: object) -> uuid.UUID:
    from sqlalchemy.ext.asyncio import AsyncEngine

    assert isinstance(engine, AsyncEngine)
    tenant_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO plans (id, key, name, limits) "
                "VALUES (:id, :key, 'Plan', '{}'::jsonb) ON CONFLICT DO NOTHING"
            ),
            {"id": plan_id, "key": f"plan-{plan_id.hex[:8]}"},
        )
        await connection.execute(
            text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :plan)"),
            {"id": tenant_id, "slug": f"t-{tenant_id.hex[:8]}", "plan": plan_id},
        )
    return tenant_id

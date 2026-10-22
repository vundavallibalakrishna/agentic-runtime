"""pgvector recall respects tenant RLS. Spec: docs/03-specs/11-memory.md §3."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ar_common.vectors import unit_vector
from ar_domain.memory.pg import RECALL_SQL

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


def _alembic(url: str) -> None:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url)
    return url


async def test_recall_sql_stays_inside_the_tenant(database_url: str) -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    plan_id = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    fact_a = uuid.uuid4()
    fact_b = uuid.uuid4()
    vector = "[" + ",".join(str(item) for item in unit_vector("status notes", 1024)) + "]"
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
                "INSERT INTO users (id, tenant_id, idp_subject, email, display_name) VALUES "
                "(:a, :tenant_a, 'a@example.com', 'a@example.com', 'A'), "
                "(:b, :tenant_b, 'b@example.com', 'b@example.com', 'B')"
            ),
            {"a": user_a, "tenant_a": tenant_a, "b": user_b, "tenant_b": tenant_b},
        )
        await connection.execute(
            text(
                "INSERT INTO memory_facts "
                "(id, tenant_id, scope, user_id, content, category, embedding, source_kind) "
                "VALUES (:id, :tenant, 'user', :user, :content, 'preference', "
                "CAST(:vector AS vector), 'explicit')"
            ),
            [
                {
                    "id": fact_a,
                    "tenant": tenant_a,
                    "user": user_a,
                    "content": "Prefers status notes under one page.",
                    "vector": vector,
                },
                {
                    "id": fact_b,
                    "tenant": tenant_b,
                    "user": user_b,
                    "content": "Prefers status notes under one page.",
                    "vector": vector,
                },
            ],
        )
    sql = RECALL_SQL.replace("ANY(CAST(:team_ids AS uuid[]))", "ANY('{}'::uuid[])")
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(tenant_a)},
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        rows = (
            await connection.execute(
                text(sql),
                {
                    "query": vector,
                    "tenant": str(tenant_a),
                    "user_id": str(user_a),
                    "agent_id": str(uuid.uuid4()),
                },
            )
        ).all()
        visible = await connection.scalar(text("SELECT count(*) FROM memory_facts"))
    await engine.dispose()
    assert visible == 1
    assert [row[0] for row in rows] == [fact_a]
    assert rows[0][2] > 0.9

"""Published skill versions are immutable and stay inside the tenant."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

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


async def test_skill_version_trigger_and_rls(database_url: str) -> None:
    tenant = uuid.uuid4()
    other = uuid.uuid4()
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    skill_id = uuid.uuid4()
    draft_id = uuid.uuid4()
    published_id = uuid.uuid4()
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
                "INSERT INTO tenants (id, slug, name, plan_id) VALUES "
                "(:id, :slug, 'A', :plan), (:other, :other_slug, 'B', :plan)"
            ),
            {
                "id": tenant,
                "slug": f"a-{tenant.hex[:8]}",
                "other": other,
                "other_slug": f"b-{other.hex[:8]}",
                "plan": plan_id,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO users (id, tenant_id, idp_subject, email, display_name) "
                "VALUES (:id, :tenant, :subject, :email, 'A')"
            ),
            {
                "id": user_id,
                "tenant": tenant,
                "subject": f"{user_id.hex[:8]}@example.com",
                "email": f"{user_id.hex[:8]}@example.com",
            },
        )
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        await connection.execute(
            text(
                "INSERT INTO skills (id, tenant_id, slug, name, description, owner_user_id) "
                "VALUES (:id, :tenant, 'briefing', 'Briefing', 'A short skill.', :user)"
            ),
            {"id": skill_id, "tenant": tenant, "user": user_id},
        )
        await connection.execute(
            text(
                "INSERT INTO skill_versions "
                "(id, tenant_id, skill_id, version, instructions_md, hash, created_by) "
                "VALUES (:id, :tenant, :skill, 0, 'Draft.', 'hash-0', :user)"
            ),
            {"id": draft_id, "tenant": tenant, "skill": skill_id, "user": user_id},
        )
        await connection.execute(
            text("UPDATE skill_versions SET instructions_md = 'Edited draft.' WHERE id = :id"),
            {"id": draft_id},
        )
        await connection.execute(
            text(
                "INSERT INTO skill_versions "
                "(id, tenant_id, skill_id, version, instructions_md, hash, created_by) "
                "VALUES (:id, :tenant, :skill, 1, 'Published.', 'hash-1', :user)"
            ),
            {"id": published_id, "tenant": tenant, "skill": skill_id, "user": user_id},
        )
    async with engine.connect() as connection:
        transaction = await connection.begin()
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        with pytest.raises(Exception, match="immutable"):
            await connection.execute(
                text("UPDATE skill_versions SET instructions_md = 'Changed.' WHERE id = :id"),
                {"id": published_id},
            )
        await transaction.rollback()
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(other)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        visible = await connection.scalar(text("SELECT count(*) FROM skills"))
    await engine.dispose()
    assert visible == 0

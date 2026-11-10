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


async def test_bootstrap_creates_the_tenant_its_admin_and_two_agents(migrated: str) -> None:
    """A new install gets a tenant, an admin and the two default agents: no model, no example."""
    from ar_common.settings import BaseServiceSettings, set_settings
    from ar_domain.bootstrap import bootstrap
    from ar_domain.db.engine import dispose_engines, get_engine

    os.environ["AR_DATABASE_URL"] = migrated
    os.environ["AR_PG_HOST_PORT"] = str(make_url(migrated).port or 5432)
    set_settings(BaseServiceSettings(_env_file=None))
    for _ in range(2):
        slug = await bootstrap(
            slug="acme", name="Acme", admin_email="Ada@Acme.Example", admin_name="Ada Lovelace"
        )
        assert slug == "acme"
    counts: dict[str, object] = {}
    engine = get_engine(migrated)
    async with engine.connect() as connection:
        for table in (
            "tenants",
            "users",
            "role_assignments",
            "model_providers",
            "conversations",
            "agents",
        ):
            counts[table] = await connection.scalar(text(f"SELECT count(*) FROM {table}"))  # noqa: S608 - fixed names
        person = (
            await connection.execute(
                text(
                    "SELECT t.slug, p.key, u.email, u.display_name, u.status, r.key "
                    "FROM users u JOIN tenants t ON t.id = u.tenant_id "
                    "JOIN plans p ON p.id = t.plan_id "
                    "JOIN role_assignments a ON a.principal_id = u.id "
                    "JOIN roles r ON r.id = a.role_id"
                )
            )
        ).one()
        agents = (
            await connection.execute(
                text(
                    "SELECT a.slug, a.status, u.email, v.state FROM agents a "
                    "JOIN users u ON u.id = a.owner_user_id "
                    "JOIN agent_versions v ON v.id = a.published_version_id ORDER BY a.slug"
                )
            )
        ).all()
        tools = await connection.scalar(
            text("SELECT count(*) FROM tools WHERE tenant_id IS NOT NULL")
        )
    assert counts == {
        "tenants": 1,
        "users": 1,
        "role_assignments": 1,
        "model_providers": 0,
        "conversations": 0,
        "agents": 2,
    }
    assert tuple(person) == (
        "acme",
        "self_hosted",
        "ada@acme.example",
        "Ada Lovelace",
        "active",
        "tenant_admin",
    )
    # The assistant and the builder, published, owned by the tenant's own admin.
    assert [tuple(row) for row in agents] == [
        ("assistant", "published", "ada@acme.example", "published"),
        ("builder", "published", "ada@acme.example", "published"),
    ]
    assert tools == 0, "the tool catalogue belongs to no tenant; no fixture tool is written"
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM tenants WHERE slug = 'acme'"))
    # The cached engine belongs to this test's event loop; the next test opens its own.
    await engine.dispose()
    dispose_engines()


async def test_made_up_tool_vectors_are_cleared(migrated: str) -> None:
    """Revision 0034 empties ``tool_versions.embedding``, also on an approved version."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated)
    _alembic(migrated, "downgrade", "0033")
    vector = "[" + ",".join(["0.5"] * 1024) + "]"
    async with engine.begin() as connection:
        server = await connection.scalar(
            text(
                "INSERT INTO tool_servers (slug, name, kind, status) "
                "VALUES ('m38a_vectors', 'Vectors', 'builtin', 'approved') RETURNING id"
            )
        )
        released = await connection.scalar(
            text(
                "INSERT INTO tool_server_versions (tool_server_id, version, review_status) "
                "VALUES (:server, '1.0.0', 'approved') RETURNING id"
            ),
            {"server": server},
        )
        tool = await connection.scalar(
            text(
                "INSERT INTO tools (tool_server_id, name, qualified_name) "
                "VALUES (:server, 'look', 'm38a_vectors.look') RETURNING id"
            ),
            {"server": server},
        )
        await connection.execute(
            text(
                "INSERT INTO tool_versions (tool_id, tool_server_version_id, description, "
                "description_hash, input_schema, risk_class, embedding) VALUES "
                "(:tool, :released, 'Look.', 'h', '{}'::jsonb, 'R0', CAST(:vector AS vector))"
            ),
            {"tool": tool, "released": released, "vector": vector},
        )
    _alembic(migrated, "upgrade", "head")
    async with engine.begin() as connection:
        left = await connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'tool_versions' AND column_name = 'embedding'"
            )
        )
        kept = await connection.scalar(
            text("SELECT description FROM tool_versions WHERE tool_id = :tool"), {"tool": tool}
        )
        await connection.execute(
            text("DELETE FROM tool_servers WHERE id = :server"), {"server": server}
        )
    await engine.dispose()
    assert left == 0
    assert kept == "Look.", "only the vector changes"


async def test_retired_pack_schema_drops_and_stays_gone(migrated: str) -> None:
    """Revision 0031 removes a pack schema that already exists, and is a no-op without one."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated)
    _alembic(migrated, "downgrade", "0030")
    async with engine.begin() as connection:
        await connection.execute(text("CREATE SCHEMA grc"))
        await connection.execute(text("CREATE TABLE grc.controls (id int PRIMARY KEY)"))
        await connection.execute(text("INSERT INTO grc.controls VALUES (7)"))
        await connection.execute(
            text("CREATE TABLE grc_alembic_version (version_num varchar(32) PRIMARY KEY)")
        )
        await connection.execute(text("INSERT INTO grc_alembic_version VALUES ('0002')"))
        plan_id = await connection.scalar(
            text("INSERT INTO plans (key, name) VALUES ('m30-drop', 'M30') RETURNING id")
        )
        tenant_id = await connection.scalar(
            text(
                "INSERT INTO tenants (slug, name, plan_id) "
                "VALUES ('m30-drop', 'M30', :plan_id) RETURNING id"
            ),
            {"plan_id": plan_id},
        )
        await connection.execute(
            text(
                "INSERT INTO installed_packs "
                "(tenant_id, pack_id, version, manifest, manifest_hash) "
                "VALUES (:tenant_id, 'grc', '1.1.0', '{}'::jsonb, 'm30')"
            ),
            {"tenant_id": tenant_id},
        )
        await connection.execute(
            text(
                "INSERT INTO tenant_pack_flags (tenant_id, pack_id, enabled) "
                "VALUES (:tenant_id, 'grc', true)"
            ),
            {"tenant_id": tenant_id},
        )
    _alembic(migrated, "upgrade", "head")
    async with engine.connect() as connection:
        schema = await connection.scalar(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'grc'")
        )
        version = await connection.scalar(text("SELECT to_regclass('public.grc_alembic_version')"))
        packs = await connection.scalar(
            text("SELECT count(*) FROM installed_packs WHERE pack_id = 'grc'")
        )
        flags = await connection.scalar(
            text("SELECT count(*) FROM tenant_pack_flags WHERE pack_id = 'grc'")
        )
        kept = await connection.scalar(text("SELECT count(*) FROM tenants WHERE slug = 'm30-drop'"))
    assert schema == 0
    assert version is None
    assert packs == 0
    assert flags == 0
    assert kept == 1
    _alembic(migrated, "downgrade", "0030")
    _alembic(migrated, "upgrade", "head")
    async with engine.connect() as connection:
        schema = await connection.scalar(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'grc'")
        )
    assert schema == 0
    await engine.dispose()


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
    async with engine.connect() as connection:
        policies = await connection.scalar(
            text(
                "SELECT count(*) FROM policies "
                "WHERE name = 'Seeded write approval' AND status = 'active'"
            )
        )
        mode = await connection.scalar(
            text(
                "SELECT document->'rules'->0->'approval'->'approvers'->>'mode' "
                "FROM policy_versions WHERE policy_id IN ("
                "SELECT id FROM policies WHERE name = 'Seeded write approval')"
            )
        )
        groups = await connection.scalar(
            text("SELECT count(*) FROM groups WHERE name = 'approvers'")
        )
        members = await connection.scalar(text("SELECT count(*) FROM group_members"))
    assert policies == 1
    assert mode == "users"
    assert groups == 1
    assert members == 1

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
                    "SELECT a.slug, a.status, a.owner_user_id, u.email, v.state FROM agents a "
                    "JOIN agent_versions v ON v.id = a.published_version_id "
                    "JOIN users u ON u.id = v.created_by ORDER BY a.slug"
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
    # The assistant and the builder, published. They ship with the product, so they have no
    # owner; the tenant's own admin is recorded as the author of their first version.
    assert [tuple(row) for row in agents] == [
        ("assistant", "published", None, "ada@acme.example", "published"),
        ("builder", "published", None, "ada@acme.example", "published"),
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


async def test_built_in_agents_lose_their_owner_and_built_ones_keep_theirs(migrated: str) -> None:
    """Revision 0052 clears the owner of the assistant and the builder in every tenant."""
    import uuid

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated)
    _alembic(migrated, "downgrade", "0051")
    tenants = [uuid.uuid4(), uuid.uuid4()]
    owners: dict[uuid.UUID, uuid.UUID] = {}
    async with engine.begin() as connection:
        plan = await connection.scalar(
            text(
                "INSERT INTO plans (key, name) VALUES ('m0052', 'Owner check') "
                "ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name RETURNING id"
            )
        )
        for tenant in tenants:
            owner = uuid.uuid4()
            owners[tenant] = owner
            await connection.execute(
                text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :p)"),
                {"id": tenant, "slug": f"own{tenant.hex[:10]}", "p": plan},
            )
            await connection.execute(
                text(
                    "INSERT INTO users (id, tenant_id, idp_subject, email, display_name, status) "
                    "VALUES (:id, :tenant, :subject, :email, 'Owner', 'active')"
                ),
                {
                    "id": owner,
                    "tenant": tenant,
                    "subject": f"idp-{owner.hex[:8]}",
                    "email": f"{owner.hex[:8]}@own.example",
                },
            )
            for slug in ("assistant", "builder", "helpdesk"):
                await connection.execute(
                    text(
                        "INSERT INTO agents (tenant_id, slug, name, owner_user_id, status) "
                        "VALUES (:tenant, :slug, :name, :owner, 'draft')"
                    ),
                    {"tenant": tenant, "slug": slug, "name": slug.title(), "owner": owner},
                )
    held = text(
        "SELECT tenant_id, slug, owner_user_id FROM agents "
        "WHERE tenant_id = ANY(:tenants) ORDER BY slug"
    )
    try:
        _alembic(migrated, "upgrade", "head")
        async with engine.begin() as connection:
            after = (await connection.execute(held, {"tenants": tenants})).all()
        assert len(after) == 6
        for tenant, slug, owner in after:
            assert owner == (owners[tenant] if slug == "helpdesk" else None)
        # Forward-only: the earlier owner is not recorded, so downgrade leaves the rows alone.
        _alembic(migrated, "downgrade", "0051")
        async with engine.begin() as connection:
            assert (await connection.execute(held, {"tenants": tenants})).all() == after
    finally:
        _alembic(migrated, "upgrade", "head")
        async with engine.begin() as connection:
            await connection.execute(
                text("DELETE FROM tenants WHERE id = ANY(:tenants)"), {"tenants": tenants}
            )
            await connection.execute(text("DELETE FROM plans WHERE key = 'm0052'"))
        await engine.dispose()


async def test_a_seeded_assistant_gets_the_new_token_limit_and_others_keep_theirs(
    migrated: str,
) -> None:
    """Revision 0054 publishes a seeded assistant that still has the old limit again."""
    import json
    import uuid

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated)
    _alembic(migrated, "downgrade", "0053")
    # The seeded limit, a limit an administrator changed, and an administrator's version.
    cases = {
        uuid.uuid4(): ("seed", 16_000),
        uuid.uuid4(): ("without-checkpoint", 32_000),
        uuid.uuid4(): ("our own", 16_000),
    }
    async with engine.begin() as connection:
        plan = await connection.scalar(
            text(
                "INSERT INTO plans (key, name) VALUES ('m0054', 'Limit check') "
                "ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name RETURNING id"
            )
        )
        for tenant, (note, limit) in cases.items():
            user, agent, version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            await connection.execute(
                text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :p)"),
                {"id": tenant, "slug": f"lim{tenant.hex[:10]}", "p": plan},
            )
            await connection.execute(
                text(
                    "INSERT INTO users (id, tenant_id, idp_subject, email, display_name, status) "
                    "VALUES (:id, :tenant, :subject, :email, 'Admin', 'active')"
                ),
                {
                    "id": user,
                    "tenant": tenant,
                    "subject": f"idp-{user.hex[:8]}",
                    "email": f"{user.hex[:8]}@lim.example",
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, slug, name, status) "
                    "VALUES (:id, :tenant, 'assistant', 'Assistant', 'published')"
                ),
                {"id": agent, "tenant": tenant},
            )
            definition = {"instructions": "Help.", "budget": {"max_steps": 8, "max_tokens": limit}}
            await connection.execute(
                text(
                    "INSERT INTO agent_versions (id, tenant_id, agent_id, version, state, "
                    "definition, definition_hash, change_note, created_by, published_at, "
                    "published_by) VALUES (:id, :tenant, :agent, 1, 'published', "
                    "CAST(:definition AS jsonb), :hash, :note, :user, now(), :user)"
                ),
                {
                    "id": version,
                    "tenant": tenant,
                    "agent": agent,
                    "definition": json.dumps(definition),
                    "hash": "0" * 64,
                    "note": note,
                    "user": user,
                },
            )
            await connection.execute(
                text("UPDATE agents SET published_version_id = :version WHERE id = :agent"),
                {"version": version, "agent": agent},
            )
    published = text(
        "SELECT v.tenant_id, v.version, v.change_note, v.definition, "
        "(SELECT count(*) FROM agent_versions s WHERE s.agent_id = v.agent_id "
        " AND s.state = 'superseded') AS superseded "
        "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
        "WHERE a.tenant_id = ANY(:tenants) AND v.state = 'published'"
    )
    tenants = list(cases)

    async def now() -> dict[uuid.UUID, tuple[int, str, int, int]]:
        async with engine.begin() as connection:
            rows = (await connection.execute(published, {"tenants": tenants})).all()
        return {row[0]: (row[1], row[2], row[3]["budget"]["max_tokens"], row[4]) for row in rows}

    seeded, changed, own = tenants
    try:
        _alembic(migrated, "upgrade", "head")
        after = await now()
        assert after[seeded] == (2, "token-budget", 80_000, 1)
        assert after[changed] == (1, "without-checkpoint", 32_000, 0)
        assert after[own] == (1, "our own", 16_000, 0)
        async with engine.begin() as connection:
            kept = await connection.scalar(
                text(
                    "SELECT definition FROM agent_versions v JOIN agents a ON a.id = v.agent_id "
                    "WHERE a.tenant_id = :tenant AND v.version = 2"
                ),
                {"tenant": seeded},
            )
        assert kept == {"instructions": "Help.", "budget": {"max_steps": 8, "max_tokens": 80_000}}
        # Downgrade publishes the old limit again under the note the seed wrote.
        _alembic(migrated, "downgrade", "0053")
        back = await now()
        assert back[seeded] == (3, "seed", 16_000, 2)
        assert back[changed] == after[changed]
        assert back[own] == after[own]
    finally:
        _alembic(migrated, "upgrade", "head")
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE agents SET published_version_id = NULL WHERE tenant_id = ANY(:t)"),
                {"t": tenants},
            )
            await connection.execute(
                text("DELETE FROM tenants WHERE id = ANY(:tenants)"), {"tenants": tenants}
            )
            await connection.execute(text("DELETE FROM plans WHERE key = 'm0054'"))
        await engine.dispose()


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

"""Scoped permissions and revision 0046 survive a database round trip."""

from __future__ import annotations

import os
import subprocess
import uuid

import orjson
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.logic import definition_hash
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.seed import apply
from ar_domain.runs.request import permissions_of

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


def _alembic(url: str, *revision: str) -> None:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", *revision],  # noqa: S607
        check=True,
        env=env,
    )


async def test_scoped_permissions_reload_from_postgres(postgres_url: str) -> None:
    url = _async_url(postgres_url)
    _alembic(url, "upgrade", "head")
    engine = create_async_engine(url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    store = ChatService()
    binding = await bind_store(store, url, tenant_slug="dev")
    assert binding is not None
    from ar_domain.agents.service import AgentLifecycle

    admin = binding.users["admin@dev.local"]
    AgentLifecycle(store).ensure_builtins(binding.tenant_id, admin)
    agent = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    posted = store.create_api_run(
        binding.tenant_id,
        admin,
        uuid.UUID(str(agent["id"])),
        "scoped",
        callback_url=None,
        on_behalf_of=None,
        allow_on_behalf=False,
        permissions=["chat:use"],
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))  # type: ignore[index]
    await flush_store(store)
    await store.durable_engine.dispose()  # type: ignore[attr-defined]

    reloaded = ChatService()
    again = await bind_store(reloaded, url, tenant_slug="dev")
    assert again is not None
    loaded = reloaded.runs[run_id]
    assert "permissions" not in loaded or loaded.get("permissions") == ["chat:use"]
    assert permissions_of(loaded) == ["chat:use"]
    await reloaded.durable_engine.dispose()  # type: ignore[attr-defined]


async def test_0046_upgrade_and_downgrade_on_seeded_data(postgres_url: str) -> None:
    url = _async_url(postgres_url)
    _alembic(url, "upgrade", "head")
    engine = create_async_engine(url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    _alembic(url, "downgrade", "0045")
    import psycopg

    definition = {
        "tools": [
            {"server": "general", "version": "*", "include": ["code", "fetch", "http", "search"]}
        ]
    }
    digest = definition_hash(definition)
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    agent = uuid.uuid4()
    version = uuid.uuid4()
    slug = f"r5{tenant.hex[:10]}"
    libpq = url.replace("postgresql+asyncpg", "postgresql", 1)
    with psycopg.connect(libpq, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO tenants (id, slug, name, plan_id) "
            "SELECT %s, %s, 'Round 5', plan_id FROM tenants WHERE slug = 'dev'",
            (tenant, slug),
        )
        conn.execute(
            "INSERT INTO users (id, tenant_id, idp_subject, email, display_name, status) "
            "VALUES (%s, %s, %s, %s, 'Owner', 'active')",
            (user, tenant, f"idp-{user.hex[:8]}", f"{slug}@dev.local"),
        )
        conn.execute(
            "INSERT INTO agents (id, tenant_id, slug, name, owner_user_id, status) "
            "VALUES (%s, %s, 'assistant', 'Assistant', %s, 'published')",
            (agent, tenant, user),
        )
        conn.execute(
            "INSERT INTO agent_versions (id, tenant_id, agent_id, version, state, definition, "
            "definition_hash, change_note, created_by, published_at, published_by) "
            "VALUES (%s, %s, %s, 1, 'published', %s::jsonb, %s, 'seed', %s, now(), %s)",
            (version, tenant, agent, orjson.dumps(definition).decode(), digest, user, user),
        )
        conn.execute(
            "UPDATE agents SET published_version_id = %s WHERE id = %s",
            (version, agent),
        )
    try:
        _alembic(url, "upgrade", "0046")
        with psycopg.connect(libpq) as conn:
            row = conn.execute(
                "SELECT v.change_note, v.definition "
                "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
                "WHERE a.id = %s",
                (agent,),
            ).fetchone()
        assert row is not None
        assert row[0] == "offline-default"
        include = row[1]["tools"][0]["include"]
        assert "fetch" not in include
        assert "http" not in include
        assert "search" not in include
        _alembic(url, "downgrade", "0045")
        with psycopg.connect(libpq) as conn:
            row = conn.execute(
                "SELECT v.change_note, v.definition "
                "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id "
                "WHERE a.id = %s",
                (agent,),
            ).fetchone()
        assert row is not None
        assert row[0] == "seed"
        assert {"fetch", "http", "search"} <= set(row[1]["tools"][0]["include"])
    finally:
        _alembic(url, "upgrade", "head")

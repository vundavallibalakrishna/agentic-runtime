"""Saved queries and sign-offs survive a database round trip, and 0049 and 0050 go up and down."""

from __future__ import annotations

import os
import subprocess
import uuid

import orjson
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.agents.logic import definition_hash
from ar_domain.approvals.reviews import ReviewBook
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.spreadsheet.saved import SETTING, SavedQueryBook

pytestmark = pytest.mark.integration

_NEW = {"sample_table", "save_query", "list_saved_queries", "run_saved_query"}


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


async def test_a_signed_saved_query_reloads_from_postgres(postgres_url: str) -> None:
    url = _async_url(postgres_url)
    _alembic(url, "upgrade", "head")
    engine = create_async_engine(url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    store = ChatService()
    binding = await bind_store(store, url, tenant_slug="dev")
    assert binding is not None
    tenant_id = binding.tenant_id
    author = binding.users["admin@dev.local"]
    approver = Actor(tenant_id, uuid.uuid4(), PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    queue = ReviewBook(store).create_queue(
        approver,
        {
            "slug": f"queries-{uuid.uuid4().hex[:8]}",
            "name": "Query sign-off",
            "subject_type": "saved_query",
            "levels": [{"level": 1, "required_count": 1}],
        },
    )
    store.tenant_settings.setdefault(tenant_id, {})["approvals"] = {SETTING: str(queue["id"])}
    book = SavedQueryBook(store)
    name = f"count-{uuid.uuid4().hex[:8]}"
    first, created = book.save(
        tenant_id, author, name=name, sql="SELECT COUNT(*) AS n FROM items", description="Rows"
    )
    assert created is True
    assert book.sign_off(tenant_id, first).status == "pending"
    item = next(row for row in store.review_items.values() if row.get("subject_id") == first["id"])
    detail = ReviewBook(store).get_item(approver, uuid.UUID(str(item["id"])))
    ReviewBook(store).decide(
        approver,
        uuid.UUID(str(item["id"])),
        {
            "decision": "approve",
            "comment": "read and agreed",
            "content_hash": detail["content_hash"],
            "statement_hash": detail["statement_hash"],
        },
        stepped_up=True,
    )
    second, _created = book.save(
        tenant_id,
        author,
        name=name,
        sql="SELECT COUNT(*) AS n FROM items WHERE amount > 10",
        description="Rows",
    )
    await flush_store(store)
    assert store.durable_engine is not None
    await store.durable_engine.dispose()

    reloaded = ChatService()
    again = await bind_store(reloaded, url, tenant_slug="dev")
    assert again is not None
    reloaded.tenant_settings.setdefault(tenant_id, {})["approvals"] = {SETTING: str(queue["id"])}
    loaded = SavedQueryBook(reloaded)
    held = loaded.versions(tenant_id, name)
    assert [row["version"] for row in held] == [1, 2]
    assert held[0]["sql"] == "SELECT COUNT(*) AS n FROM items"
    assert held[0]["content_hash"] == first["content_hash"]
    signs = [row for row in reloaded.signoffs.values() if row.get("review_item_id") == item["id"]]
    assert len(signs) == 1
    assert signs[0]["decision"] == "approve"
    assert signs[0]["comment"] == "read and agreed"
    assert signs[0]["signer_principal_id"] == approver.user_id
    # The first version is still signed after a restart; the amended one still waits.
    state = loaded.sign_off(tenant_id, held[0])
    assert state.status == "signed"
    assert state.approved_at is not None
    assert loaded.sign_off(tenant_id, held[1]).status == "pending"
    assert held[1]["id"] == second["id"]
    assert reloaded.durable_engine is not None
    await reloaded.durable_engine.dispose()


async def test_0049_and_0050_upgrade_and_downgrade_on_seeded_data(postgres_url: str) -> None:
    url = _async_url(postgres_url)
    _alembic(url, "upgrade", "head")
    engine = create_async_engine(url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    _alembic(url, "downgrade", "0048")
    import psycopg

    definition: dict[str, object] = {
        "tools": [{"server": "general", "version": "*", "include": ["code", "query_table"]}]
    }
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    agent = uuid.uuid4()
    version = uuid.uuid4()
    slug = f"sq{tenant.hex[:10]}"
    libpq = url.replace("postgresql+asyncpg", "postgresql", 1)
    with psycopg.connect(libpq, autocommit=True) as conn:
        assert conn.execute("SELECT to_regclass('saved_queries')").fetchone() == (None,)
        conn.execute(
            "INSERT INTO tenants (id, slug, name, plan_id) "
            "SELECT %s, %s, 'Saved queries', plan_id FROM tenants WHERE slug = 'dev'",
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
            "VALUES (%s, %s, %s, 1, 'published', %s::jsonb, %s, 'offline-default', %s, now(), %s)",
            (
                version,
                tenant,
                agent,
                orjson.dumps(definition).decode(),
                definition_hash(definition),
                user,
                user,
            ),
        )
        conn.execute("UPDATE agents SET published_version_id = %s WHERE id = %s", (version, agent))
    published = (
        "SELECT v.change_note, v.definition "
        "FROM agents a JOIN agent_versions v ON v.id = a.published_version_id WHERE a.id = %s"
    )
    try:
        _alembic(url, "upgrade", "head")
        with psycopg.connect(libpq) as conn:
            row = conn.execute(published, (agent,)).fetchone()
            assert conn.execute("SELECT to_regclass('saved_queries')").fetchone() != (None,)
        assert row is not None
        assert row[0] == "sample-and-saved-queries"
        grants = {item["server"]: item["include"] for item in row[1]["tools"]}
        assert _NEW <= set(grants["general"])
        assert grants["knowledge"] == ["search"]
        _alembic(url, "downgrade", "0048")
        with psycopg.connect(libpq) as conn:
            row = conn.execute(published, (agent,)).fetchone()
        assert row is not None
        assert row[0] == "offline-default"
        grants = {item["server"]: item["include"] for item in row[1]["tools"]}
        assert grants == {"general": ["code", "query_table"]}
    finally:
        _alembic(url, "upgrade", "head")

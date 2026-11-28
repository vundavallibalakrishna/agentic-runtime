"""Real Postgres: bounded pages, literal filters, keyset traversal and caller RLS."""

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, insert, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.errors import InvalidCursorError
from ar_common.ids import new_id
from ar_domain.agents.tables import Agent, AgentVersion
from ar_domain.conversations.repository import ConversationRepository
from ar_domain.conversations.tables import Conversation
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.identity.models import Plan, Tenant, User

pytestmark = pytest.mark.integration
_CURSOR_KEY = "pagination-integration-secret-for-tests"


async def _seed(url: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    engine = create_async_engine(url)
    plan, tenant, user, other_user, other_tenant, agent, version = (new_id() for _ in range(7))
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            insert(Plan).values(id=plan, key=str(plan), name="Page test", limits={})
        )
        for identity in [tenant, other_tenant]:
            await session.execute(
                insert(Tenant).values(
                    id=identity,
                    plan_id=plan,
                    slug=f"page-{identity.hex}",
                    name="Page test",
                    settings={},
                )
            )
        for identity in [user, other_user]:
            await session.execute(
                insert(User).values(
                    id=identity,
                    tenant_id=tenant,
                    idp_subject=str(identity),
                    email=f"{identity}@test.invalid",
                    display_name="Page owner",
                )
            )
        await session.execute(
            insert(Agent).values(id=agent, tenant_id=tenant, slug="page-agent", name="Page agent")
        )
        await session.execute(
            insert(AgentVersion).values(
                id=version,
                tenant_id=tenant,
                agent_id=agent,
                version=1,
                definition={},
                definition_hash="page-test",
            )
        )
        params = {
            "tenant": tenant,
            "user": user,
            "agent": agent,
            "version": version,
            "stamp": datetime.now(UTC) - timedelta(hours=1),
        }
        await session.execute(
            text("""
            INSERT INTO conversations (id,tenant_id,user_id,agent_id,title,created_at,updated_at)
            SELECT uuidv7(), :tenant, :user, :agent, 'Page query_% ' || g, :stamp, :stamp
            FROM generate_series(1,100000) g
        """),
            params,
        )
        conversation = await session.scalar(
            text("SELECT id FROM conversations WHERE tenant_id=:tenant LIMIT 1"), params
        )
        await session.execute(
            text("""
            INSERT INTO runs (id,tenant_id,user_id,conversation_id,agent_id,agent_version_id,
                root_run_id,trigger,initiator_type,temporal_workflow_id,budget,status,result_summary,created_at,updated_at)
            SELECT id,:tenant,:user,:conversation,:agent,:version,id,'chat','user','page-'||id,
                '{}'::jsonb,CASE WHEN g%2=0 THEN 'failed' ELSE 'completed' END,
                'Page result_% '||g,:stamp,:stamp
            FROM (SELECT uuidv7() id, g FROM generate_series(1,100000) g) entries
        """),
            {**params, "conversation": conversation},
        )
        await session.execute(
            insert(Conversation).values(
                tenant_id=tenant,
                user_id=user,
                agent_id=agent,
                title="Hidden preview",
                is_preview=True,
            )
        )
        await session.execute(
            insert(Conversation).values(
                tenant_id=tenant,
                user_id=user,
                agent_id=agent,
                title="Deleted",
                deleted_at=datetime.now(UTC),
            )
        )
        await session.execute(text("ANALYZE conversations"))
        await session.execute(text("ANALYZE runs"))
    await engine.dispose()
    return tenant, user, other_user, other_tenant


@pytest.fixture(scope="module")
def paged_database(postgres_url: str) -> tuple[str, tuple[uuid.UUID, ...]]:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    env = {**os.environ, "AR_DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],
        check=True,
        env=env,
    )
    identities = asyncio.run(_seed(url))
    app_url = make_url(url).set(username="ar_app", password=os.environ["AR_DB_APP_PASSWORD"])
    return app_url.render_as_string(hide_password=False), identities


def _ctx(tenant: uuid.UUID, user: uuid.UUID) -> TenantContext:
    return TenantContext.from_principal(
        Principal(kind="user", id=str(user), tenant_id=tenant, permissions=frozenset({"chat:use"})),
        "pagination-integration",
    )


async def test_100k_pages_never_hydrate_or_cross_callers(paged_database: tuple) -> None:
    url, (tenant, user, other_user, other_tenant) = paged_database
    engine = create_async_engine(url)
    owner = _ctx(tenant, user)
    cursor = None
    seen: set[uuid.UUID] = set()
    pages = 0
    while True:
        async with tenant_session(owner, engine=engine) as session:
            page = await ConversationRepository(session, owner).page(
                "conversations", secret=_CURSOR_KEY, limit=200, cursor=cursor
            )
        assert len(page.items) == 200
        ids = {row["id"] for row in page.items}
        assert not seen.intersection(ids)
        assert all(row["tenant_id"] == tenant and row["user_id"] == user for row in page.items)
        seen.update(ids)
        pages += 1
        cursor = page.next_cursor
        if not cursor:
            break
    assert len(seen) == 100000 and pages == 500
    async with tenant_session(owner, engine=engine) as session:
        repository = ConversationRepository(session, owner)
        found = await repository.page(
            "conversations", secret=_CURSOR_KEY, q="query_% 100000", limit=25
        )
        assert len(found.items) == 1 and found.items[0]["title"] == "Page query_% 100000"
        first = await repository.page("runs", secret=_CURSOR_KEY, limit=25, status="failed")
        assert len(first.items) == 25 and all(row["status"] == "failed" for row in first.items)
        following = await repository.page(
            "runs", secret=_CURSOR_KEY, limit=25, status="failed", cursor=first.next_cursor
        )
        assert not {row["id"] for row in first.items}.intersection(
            row["id"] for row in following.items
        )
        match = await repository.page("runs", secret=_CURSOR_KEY, q="result_% 100000")
        assert len(match.items) == 1
        with pytest.raises(InvalidCursorError):
            await repository.page("conversations", secret=_CURSOR_KEY, cursor=first.next_cursor)
        with pytest.raises(InvalidCursorError):
            await repository.page("runs", secret=_CURSOR_KEY, q="changed", cursor=first.next_cursor)
        with pytest.raises(InvalidCursorError):
            await repository.page("runs", secret=_CURSOR_KEY, cursor="tampered")
        plan = await session.scalar(
            text("""EXPLAIN (FORMAT JSON) SELECT id FROM conversations
            WHERE tenant_id=:tenant AND user_id=:user AND deleted_at IS NULL
            ORDER BY updated_at DESC, id DESC LIMIT 201"""),
            {"tenant": tenant, "user": user},
        )
        assert "ix_conversations_caller_page" in str(plan)
    for context in [_ctx(tenant, other_user), _ctx(other_tenant, user)]:
        async with tenant_session(context, engine=engine) as session:
            repository = ConversationRepository(session, context)
            assert not (await repository.page("conversations", secret=_CURSOR_KEY)).items
            assert not (await repository.page("runs", secret=_CURSOR_KEY)).items
            with pytest.raises(InvalidCursorError):
                await repository.page(
                    "runs", secret=_CURSOR_KEY, status="failed", cursor=first.next_cursor
                )
    await engine.dispose()


async def test_screen_metadata_does_not_load_100k_history(paged_database: tuple) -> None:
    from ar_domain.readmodel.model import RepositoryReadModel

    url, (tenant, user, _, _) = paged_database
    engine = create_async_engine(url)
    statements: list[str] = []

    def capture(connection, cursor, statement, parameters, context, many):
        statements.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    model = RepositoryReadModel(database_url=url)
    model.engine = engine
    for projection in ["agents", "models", "settings"]:
        async with model.open(
            tenant, user_id=str(user), commit=False, projection=projection
        ) as unit:
            assert not unit.conversations and not unit.runs and not unit.messages
            if projection == "agents":
                assert len(unit.agents) == 1
    event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert not any(
        "from conversations" in statement
        or "from runs" in statement
        or "from messages" in statement
        for statement in statements
    )
    await engine.dispose()

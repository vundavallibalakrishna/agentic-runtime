"""An eval run started in one process can be carried out by another.

The worker reads the run from the database. The agent, the tags and the choice to replace
every tool were kept only in the process that started the run, so the worker failed on
every run and a required suite could never let a publish through.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.durable.hydrate import hydrate_tenant
from ar_domain.evals.book import EvalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def test_the_worker_reads_the_agent_tags_and_tool_choice_of_a_run(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    api = ChatService()
    assert await bind_store(api, database_url, tenant_slug="dev") is not None
    tenant = api.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(api.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")
    slug = f"scored-{uuid.uuid4().hex[:8]}"
    created = AgentLifecycle(api).create(actor, slug=slug, name="Scored", description="evals")
    agent_id = uuid.UUID(str(created["id"]))
    book = EvalBook(api)
    suite = book.create_suite(actor, {"name": f"Suite {slug}", "agent_id": agent_id})
    started = book.start_run(
        actor,
        uuid.UUID(str(suite["id"])),
        {
            "agent_id": agent_id,
            "agent_version_ref": "draft",
            "tags": ["safety"],
            "mock_all_tools": True,
        },
    )
    run_id = uuid.UUID(str(started["id"]))
    await flush_store(api)

    worker = ChatService()
    assert await bind_store(worker, database_url, tenant_slug="dev") is not None
    await hydrate_tenant(worker, engine, tenant)
    loaded = worker.eval_runs[run_id]
    assert loaded["agent_id"] == agent_id
    assert loaded["tags"] == ["safety"]
    assert loaded["mock_all_tools"] is True
    assert loaded["agent_version_id"] == api.eval_runs[run_id]["agent_version_id"]
    # The database is shared with the other tests of this run: leave it as it was found.
    async with AsyncSession(engine) as session, session.begin():
        for statement in (
            "DELETE FROM eval_runs WHERE id = :run",
            "DELETE FROM eval_suites WHERE id = :suite",
            "UPDATE agents SET draft_version_id = NULL, published_version_id = NULL "
            "WHERE id = :agent",
            "DELETE FROM agent_versions WHERE agent_id = :agent",
            "DELETE FROM agents WHERE id = :agent",
        ):
            await session.execute(
                text(statement), {"run": run_id, "suite": suite["id"], "agent": agent_id}
            )
    await engine.dispose()

"""HTTP product rows survive a process restart once Postgres is bound."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.knowledge.book import KnowledgeBook

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


async def test_bind_flushes_chat_knowledge_memory_and_skills(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    store = ChatService()
    binding = await bind_store(store, database_url)
    assert binding is not None
    assert binding.tenant_id == demo_id("tenant")
    assert store.durable is True
    admin_id = binding.users["admin@dev.local"]
    actor = Actor(binding.tenant_id, admin_id, PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    created = KnowledgeBook(store).create_collection(
        actor, {"slug": "handbook", "name": "Handbook"}
    )
    fact_id = uuid.uuid4()
    store.memory_facts[fact_id] = {
        "id": fact_id,
        "tenant_id": binding.tenant_id,
        "scope": "user",
        "user_id": admin_id,
        "content": "The desk opens at 08:30.",
        "category": "fact",
        "source_kind": "explicit",
        "trust_level": "high",
        "confidence": 1.0,
        "status": "active",
    }
    skill_id = uuid.uuid4()
    store.skills[skill_id] = {
        "id": skill_id,
        "tenant_id": binding.tenant_id,
        "slug": "desk-hours",
        "name": "Desk hours",
        "description": "When the desk opens",
        "owner_user_id": admin_id,
        "visibility": "tenant",
        "status": "draft",
    }
    await flush_store(store)
    async with engine.connect() as connection:
        agents = await connection.scalar(
            text("SELECT count(*) FROM agents WHERE tenant_id = :tenant"),
            {"tenant": binding.tenant_id},
        )
        collections = await connection.scalar(
            text("SELECT count(*) FROM knowledge_collections WHERE slug = 'handbook'"),
        )
        facts = await connection.scalar(
            text("SELECT count(*) FROM memory_facts WHERE id = :id"),
            {"id": fact_id},
        )
        skills = await connection.scalar(
            text("SELECT count(*) FROM skills WHERE id = :id"),
            {"id": skill_id},
        )
    await engine.dispose()
    assert agents >= 1
    assert collections == 1
    assert facts == 1
    assert skills == 1
    assert created["slug"] == "handbook"

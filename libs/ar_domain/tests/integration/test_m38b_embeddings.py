"""Which model wrote a vector is saved with it, and a restarted process knows.

Task: M38b-T07b. A collection and a memory fact record the embedding model that wrote
their vectors. A process that starts later compares and extends them with that model.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.embedding import collection_dims, collection_model
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.vectors import MemoryVectors
from ar_testing.stand_in import EMBEDDING_MODEL, shared

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)
    url = url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def _process(database_url: str) -> ChatService:
    """A product store attached to the dev tenant, as one API or worker process holds it."""
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    return store


async def test_a_restarted_process_knows_which_model_wrote_each_vector(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    first = await _process(database_url)
    binding = first.tenant_binding
    assert binding is not None
    tenant = binding.tenant_id
    actor = Actor(
        tenant, binding.users["admin@dev.local"], PERMISSION_KEYS, roles=frozenset({"tenant_admin"})
    )

    # The database is shared with the other integration tests, so this test asserts only
    # on what it registers and creates. The refusal without a model is a unit test.
    model_id = await shared().save_embeddings(first, tenant)
    created = KnowledgeBook(first).create_collection(actor, {"slug": "bay", "name": "Bay"})
    fact = MemoryBook(first).create_user(actor, {"content": "The loading bay closes at six"})
    await flush_store(first)

    async with engine.connect() as connection:
        saved = (
            await connection.execute(
                text(
                    "SELECT embedding_alias, embedding_model, embedding_model_id "
                    "FROM knowledge_collections WHERE id = :id"
                ),
                {"id": uuid.UUID(str(created["id"]))},
            )
        ).one()
        fact_model = await connection.scalar(
            text("SELECT embedding_model_id FROM memory_facts WHERE id = :id"),
            {"id": uuid.UUID(str(fact["id"]))},
        )
    assert tuple(saved) == ("embed", EMBEDDING_MODEL, model_id)
    assert fact_model == model_id

    # A process that starts later reads the same registry and the same records.
    restarted = await _process(database_url)
    row = restarted.knowledge_collections[uuid.UUID(str(created["id"]))]
    assert collection_model(restarted, row).model_id == model_id
    assert collection_dims(row) == 1024
    fact_row = restarted.memory_facts[uuid.UUID(str(fact["id"]))]
    assert len(MemoryVectors(restarted, tenant).of(fact_row)) == 1024
    found = MemoryBook(restarted).list_user(actor, query="when does the loading bay close")
    assert fact["id"] in [item["id"] for item in found]

    for store in (first, restarted):
        if store.durable_engine is not None:
            await store.durable_engine.dispose()
    await engine.dispose()

"""A re-index on a database-backed install: asked for in one process, done in another.

The API's store queues the re-index; the ingest worker's store, bound to the same database
and object store, runs ``ReindexCollectionWorkflow`` on the time-skipping server. The
database then holds only the new version's passages and pgvector rows, and the API's store
searches the new version once it has read the collection again.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from temporalio.worker import Worker

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.durable.hydrate import refresh_knowledge
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.members import add_member
from ar_ingest.activities import bind_store as bind_ingest
from ar_ingest.main import TASK_QUEUE
from ar_ingest.worker import ingest_activities
from ar_ingest.workflows.reindex_collection import ReindexCollectionWorkflow
from ar_testing.objects import MemoryObjectStore
from ar_testing.stand_in import shared

if TYPE_CHECKING:
    from temporalio.testing import WorkflowEnvironment

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


async def _bound(database_url: str, objects: MemoryObjectStore) -> ChatService:
    store = ChatService()
    store.objects = objects  # type: ignore[attr-defined]
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    return store


async def _versions(engine: object, collection_id: uuid.UUID) -> tuple[set[int], set[int]]:
    """The index versions of the collection's passages and of its pgvector rows."""
    async with engine.connect() as connection:  # type: ignore[attr-defined]
        passages = await connection.execute(
            text(
                "SELECT DISTINCT c.index_version FROM document_chunks c "
                "JOIN documents d ON d.id = c.document_id WHERE d.collection_id = :id"
            ),
            {"id": collection_id},
        )
        vectors = await connection.execute(
            text("SELECT DISTINCT index_version FROM chunk_embeddings WHERE collection_id = :id"),
            {"id": collection_id},
        )
        return {row[0] for row in passages}, {row[0] for row in vectors}


async def test_a_reindex_queued_by_the_api_is_done_by_the_worker_and_read_back(
    database_url: str, temporal_env: WorkflowEnvironment
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    objects = MemoryObjectStore()
    api = await _bound(database_url, objects)
    tenant = api.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(api.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    await shared().save_embeddings(api, tenant)
    book = KnowledgeBook(api)
    slug = f"rooms-{uuid.uuid4().hex[:8]}"
    collection_id = uuid.UUID(
        str(book.create_collection(actor, {"name": slug, "slug": slug})["id"])
    )
    for n in range(3):
        await add_member(
            api,
            actor,
            collection_id,
            {"kind": "text", "title": f"Room {n}", "text": f"Room {n} is on floor {n + 4}."},
        )
    await flush_store(api)
    assert await _versions(engine, collection_id) == ({1}, {1})

    worker = await _bound(database_url, objects)
    worker._ingest_worker = True
    bind_ingest(worker)
    api.temporal_client = temporal_env.client
    async with Worker(
        temporal_env.client,
        task_queue=TASK_QUEUE,
        workflows=[ReindexCollectionWorkflow],
        activities=ingest_activities(),
    ):
        queued = await book.reindex_collection(
            actor, collection_id, {"chunking": {"contextual": True}}
        )
        # The API's request saved the job and changed nothing in the collection.
        assert api.knowledge_collections[collection_id]["index_version"] == 1
        result = await temporal_env.client.get_workflow_handle(f"reindex-{collection_id}").result()
    assert result["status"] == "succeeded"

    # The database holds only the new version, in the passages and in pgvector.
    assert await _versions(engine, collection_id) == ({2}, {2})
    async with engine.connect() as connection:
        collection = (
            (
                await connection.execute(
                    text(
                        "SELECT index_version, chunking FROM knowledge_collections WHERE id = :id"
                    ),
                    {"id": collection_id},
                )
            )
            .mappings()
            .one()
        )
        job = (
            (
                await connection.execute(
                    text("SELECT status, stats, error FROM ingestion_jobs WHERE id = :id"),
                    {"id": uuid.UUID(queued["job_id"])},
                )
            )
            .mappings()
            .one()
        )
    assert collection["index_version"] == 2
    assert collection["chunking"]["contextual"] is True
    assert job["status"] == "succeeded"
    assert job["error"] is None
    assert job["stats"]["updated"] == 3

    # The API's store reads the new version and answers from it.
    await refresh_knowledge(api, tenant)
    assert api.knowledge_collections[collection_id]["index_version"] == 2
    found = book.search(
        actor, {"query": "Which floor is room 2 on?", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "Room 2" for hit in found["hits"])  # type: ignore[union-attr]
    await engine.dispose()

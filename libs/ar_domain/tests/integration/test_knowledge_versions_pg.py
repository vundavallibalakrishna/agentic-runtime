"""A knowledge document's versions and its source's sync state survive the process.

One store fetches two versions and saves; a second store, bound to the same database and
object store, reads the versions, the newest bytes, the earlier bytes and the source's
cursor. Another tenant sees none of the rows.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.durability.store import read_blob
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.pipeline import stored_bytes
from ar_domain.knowledge.raw import keep_raw, revisions_of
from ar_domain.knowledge.syncing import _stub
from ar_testing.objects import MemoryObjectStore
from ar_testing.stand_in import shared

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


async def test_versions_and_sync_state_are_read_back_by_another_process(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    objects = MemoryObjectStore()
    first = await _bound(database_url, objects)
    tenant = first.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(first.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    await shared().save_embeddings(first, tenant)
    book = KnowledgeBook(first)
    slug = f"watched-{uuid.uuid4().hex[:8]}"
    collection = book.create_collection(actor, {"name": slug, "slug": slug})
    made = book.create_source(
        actor,
        uuid.UUID(str(collection["id"])),
        {"name": "Notice", "kind": "web", "config": {}, "sync_schedule": "0 7 * * *"},
    )
    source = first.knowledge_sources[uuid.UUID(str(made["id"]))]
    item = {"external_id": "https://example.org/notice", "title": "Notice"}
    document = _stub(first, source, item, "text/html", [f"tenant:{tenant}"])
    document["version_hash"] = "v2"
    old_file = keep_raw(first, document, b"<p>limit 10</p>", mime_type="text/html")
    new_file = keep_raw(
        first, document, b"<p>limit 25</p>", mime_type="text/html", measured={"etag": '"b"'}
    )
    source["cursor"] = {"etag": '"b"'}
    source["last_sync_at"] = utcnow()
    source["last_sync_status"] = "succeeded"
    await flush_store(first)

    second = await _bound(database_url, objects)
    document_id = uuid.UUID(str(document["id"]))
    loaded = second.knowledge_documents[document_id]
    assert loaded["raw_file_id"] == new_file
    assert stored_bytes(second, document_id) == b"<p>limit 25</p>"
    assert read_blob(second, old_file) == b"<p>limit 10</p>"
    newest, earlier = revisions_of(second, document_id)
    assert (newest["file_id"], earlier["file_id"]) == (new_file, old_file)
    assert newest["metadata"] == {"etag": '"b"'}
    kept = second.knowledge_sources[uuid.UUID(str(source["id"]))]
    assert kept["cursor"] == {"etag": '"b"'}
    assert kept["last_sync_status"] == "succeeded"
    assert kept["last_sync_at"] is not None
    assert kept["sync_schedule"] == "0 7 * * *"
    shown = KnowledgeBook(second).get_document(actor, document_id)["revisions"]
    assert [row["file_id"] for row in shown] == [str(new_file), str(old_file)]  # type: ignore[union-attr]

    async with engine.connect() as connection, connection.begin():
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(uuid.uuid4())},
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        seen = await connection.execute(text("SELECT count(*) FROM document_revisions"))
        assert seen.scalar_one() == 0
    async with engine.connect() as connection, connection.begin():
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        seen = await connection.execute(
            text("SELECT count(*) FROM document_revisions WHERE document_id = :id"),
            {"id": document_id},
        )
        assert seen.scalar_one() == 2
    await engine.dispose()

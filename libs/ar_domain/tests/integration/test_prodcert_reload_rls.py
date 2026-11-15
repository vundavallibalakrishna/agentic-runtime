"""Production-cert defect 14: a reloaded document is read under the tenant's RLS context.

The ingest worker writes "indexed" to Postgres in its own unit; the API store then calls
``reload_document`` to pick that up into the long-lived write-behind cache that listings read.
Under the production ``ar_app`` role the read is RLS-scoped, so without ``app.tenant_id`` the row
is invisible, ``reload_document`` returns early, and the document reads back "pending" for ever.

This runs the reload as ``ar_app`` (not the testcontainers superuser, which bypasses RLS) to prove
the fix, with a wrong-tenant control to prove RLS is actually enforced. Proof: integration.
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
from ar_domain.durable.hydrate import reload_document
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.knowledge.book import KnowledgeBook
from ar_testing.stand_in import shared

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


async def test_reload_document_reads_under_tenant_rls(database_url: str) -> None:
    owner = create_async_engine(database_url)
    async with AsyncSession(owner, expire_on_commit=False) as session, session.begin():
        await apply(session)

    api = ChatService(allow_loopback=True)
    binding = await bind_store(api, database_url, tenant_slug="dev")
    assert binding is not None
    tenant = binding.tenant_id
    actor = Actor(
        tenant,
        binding.users["admin@dev.local"],
        PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
    )
    await shared().save_embeddings(api, tenant)
    collection = KnowledgeBook(api).create_collection(
        actor, {"slug": "defect14-docs", "name": "Defect 14"}
    )
    added = await KnowledgeBook(api).add_member(
        actor,
        uuid.UUID(str(collection["id"])),
        {"kind": "text", "title": "Desk hours", "text": "The desk opens at 08:30."},
    )
    assert added["result"] == "indexed"
    document_id = uuid.UUID(str(added["document"]["id"]))
    await flush_store(api)

    # Postgres holds "indexed". Simulate the API store that only ever saw the pre-worker row.
    async with owner.connect() as connection:
        stored = await connection.scalar(
            text("SELECT status FROM documents WHERE id = :id"), {"id": document_id}
        )
    assert stored == "indexed"
    # The API store that only ever saw the pre-worker row: a *clean* (flushed, non-dirty)
    # "pending", the way it is after the API flushes the new document and the ingest worker
    # later advances it in Postgres. (A dirty row is deliberately not clobbered by a reload.)
    api.knowledge_documents[document_id]["status"] = "pending"
    api.knowledge_documents.dirty.discard(document_id)

    # Read the way production does: the RLS-enforced ``ar_app`` role, not the superuser.
    original_engine = api.durable_engine
    app_engine = create_async_engine(
        database_url, connect_args={"server_settings": {"role": "ar_app"}}
    )
    api.durable_engine = app_engine  # type: ignore[assignment]

    # Wrong tenant: RLS hides the row, so the stale "pending" is kept — proves RLS is enforced.
    api.context_tenant_id = uuid.uuid4()  # type: ignore[attr-defined]
    await reload_document(api, document_id)
    assert api.knowledge_documents[document_id]["status"] == "pending"

    # The real tenant: the context lets the read through and the document reads back "indexed".
    api.context_tenant_id = tenant  # type: ignore[attr-defined]
    await reload_document(api, document_id)
    assert api.knowledge_documents[document_id]["status"] == "indexed"

    await app_engine.dispose()
    await original_engine.dispose()
    await owner.dispose()

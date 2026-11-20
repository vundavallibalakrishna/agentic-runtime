"""Scoped search, library owner RLS and vector delete against Postgres."""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ar_common.vectors import unit_vector
from ar_domain.knowledge.store_pgvector import PgVectorStore
from ar_domain.knowledge.store_types import DeleteFilter, HybridQuery, IndexedChunk, SearchTarget

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


async def test_search_is_limited_to_the_named_document_and_delete_removes_it(
    database_url: str,
) -> None:
    tenant = uuid.uuid4()
    collection = uuid.uuid4()
    source = uuid.uuid4()
    kept = uuid.uuid4()
    other = uuid.uuid4()
    engine = create_async_engine(database_url)
    plan = uuid.uuid4()
    kept_chunk = _chunk(tenant, collection, source, kept, "alpha desk hours live here")
    other_chunk = _chunk(tenant, collection, source, other, "beta garden notes live here")
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO plans (id, key, name, limits) VALUES (:id, :key, 'P', '{}'::jsonb)"),
            {"id": plan, "key": f"p-{plan.hex[:8]}"},
        )
        await connection.execute(
            text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :plan)"),
            {"id": tenant, "slug": f"t-{tenant.hex[:8]}", "plan": plan},
        )
        await connection.execute(
            text(
                "INSERT INTO knowledge_collections (id, tenant_id, slug, name, store_collection) "
                "VALUES (:id, :tenant, :slug, 'Lib', 'pg')"
            ),
            {"id": collection, "tenant": tenant, "slug": f"c-{collection.hex[:8]}"},
        )
        await connection.execute(
            text(
                "INSERT INTO knowledge_sources (id, tenant_id, collection_id, name, kind) "
                "VALUES (:id, :tenant, :collection, 'up', 'upload')"
            ),
            {"id": source, "tenant": tenant, "collection": collection},
        )
        await connection.execute(
            text(
                "INSERT INTO documents (id, tenant_id, collection_id, source_id, external_id, "
                "uri, title, mime_type, version_hash) VALUES "
                "(:id, :tenant, :collection, :source, :external, 'u', 'T', 'text/plain', 'h')"
            ),
            [
                {
                    "id": document,
                    "tenant": tenant,
                    "collection": collection,
                    "source": source,
                    "external": document.hex,
                }
                for document in (kept, other)
            ],
        )
        await connection.execute(
            text(
                "INSERT INTO document_chunks (id, tenant_id, document_id, ordinal, text, "
                "token_count, index_version) VALUES (:id, :tenant, :document, 0, :text, 4, 1)"
            ),
            [
                {
                    "id": row.chunk_id,
                    "tenant": tenant,
                    "document": row.document_id,
                    "text": row.lexical_text,
                }
                for row in (kept_chunk, other_chunk)
            ],
        )
    await engine.dispose()
    store = PgVectorStore(dsn=database_url)
    await store.upsert("pg", [kept_chunk, other_chunk])
    found = await store.search(_query(kept_chunk, "desk hours", document_ids=(kept,)))
    assert {row.document_id for row in found} == {kept}
    await store.delete("pg", DeleteFilter(tenant_id=tenant, document_id=kept))
    after = await store.search(_query(kept_chunk, "desk hours", document_ids=(kept,)))
    assert after == []


async def test_library_rows_are_owner_only_under_rls(database_url: str) -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    other = uuid.uuid4()
    document = uuid.uuid4()
    plan = uuid.uuid4()
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO plans (id, key, name, limits) VALUES (:id, :key, 'P', '{}'::jsonb)"),
            {"id": plan, "key": f"p-{plan.hex[:8]}"},
        )
        await connection.execute(
            text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :plan)"),
            {"id": tenant, "slug": f"t-{tenant.hex[:8]}", "plan": plan},
        )
        await connection.execute(
            text(
                "INSERT INTO users (id, tenant_id, idp_subject, email, display_name) "
                "VALUES (:id, :tenant, :subject, :email, 'U')"
            ),
            [
                {
                    "id": user,
                    "tenant": tenant,
                    "subject": f"{user.hex}@example.com",
                    "email": f"{user.hex}@example.com",
                }
                for user in (owner, other)
            ],
        )
        await connection.execute(
            text(
                "INSERT INTO documents (id, tenant_id, owner_user_id, title, filename, "
                "mime_type, source, content_hash, version_hash, size_bytes, external_id, uri) "
                "VALUES (:id, :tenant, :owner, 'Note', 'note.md', 'text/markdown', 'upload', "
                ":hash, :hash, 12, 'library:' || :external, 'library://' || :external)"
            ),
            {
                "id": document,
                "tenant": tenant,
                "owner": owner,
                "hash": uuid.uuid4().hex,
                "external": str(document),
            },
        )
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
        )
        await connection.execute(
            text("SELECT set_config('app.user_id', :user, true)"), {"user": str(other)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        seen = await connection.scalar(
            text("SELECT count(*) FROM documents WHERE id = :id"), {"id": document}
        )
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
        )
        await connection.execute(
            text("SELECT set_config('app.user_id', :user, true)"), {"user": str(owner)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        owned = await connection.scalar(
            text("SELECT count(*) FROM documents WHERE id = :id"), {"id": document}
        )
    await engine.dispose()
    assert seen == 0
    assert owned == 1


async def test_a_collection_reader_does_not_see_the_library_extract(database_url: str) -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    reader = uuid.uuid4()
    document = uuid.uuid4()
    file_id = uuid.uuid4()
    collection = uuid.uuid4()
    source = uuid.uuid4()
    knowledge = uuid.uuid4()
    plan = uuid.uuid4()
    digest = uuid.uuid4().hex
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO plans (id, key, name, limits) VALUES (:id, :key, 'P', '{}'::jsonb)"),
            {"id": plan, "key": f"p-{plan.hex[:8]}"},
        )
        await connection.execute(
            text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :plan)"),
            {"id": tenant, "slug": f"t-{tenant.hex[:8]}", "plan": plan},
        )
        await connection.execute(
            text(
                "INSERT INTO users (id, tenant_id, idp_subject, email, display_name) "
                "VALUES (:id, :tenant, :subject, :email, 'U')"
            ),
            [
                {
                    "id": user,
                    "tenant": tenant,
                    "subject": f"{user.hex}@example.com",
                    "email": f"{user.hex}@example.com",
                }
                for user in (owner, reader)
            ],
        )
        await connection.execute(
            text(
                "INSERT INTO files (id, tenant_id, owner_user_id, kind, name, mime_type, "
                "size_bytes, sha256, object_key, status, scan_status) VALUES (:id, :tenant, "
                ":owner, 'upload', 'note.md', 'text/markdown', 12, :hash, :key, 'ready', 'clean')"
            ),
            {
                "id": file_id,
                "tenant": tenant,
                "owner": owner,
                "hash": digest,
                "key": f"t/{tenant}/upload/{file_id}",
            },
        )
        await connection.execute(
            text(
                "INSERT INTO documents (id, tenant_id, owner_user_id, title, filename, "
                "mime_type, source, content_hash, version_hash, size_bytes, external_id, uri) "
                "VALUES (:id, :tenant, :owner, 'Note', 'note.md', 'text/markdown', 'upload', "
                ":hash, :hash, 12, 'library:' || :external, 'library://' || :external)"
            ),
            {
                "id": document,
                "tenant": tenant,
                "owner": owner,
                "hash": digest,
                "external": str(document),
            },
        )
        await connection.execute(
            text(
                "INSERT INTO knowledge_collections (id, tenant_id, slug, name, store_collection) "
                "VALUES (:id, :tenant, :slug, 'Lib', 'pg')"
            ),
            {"id": collection, "tenant": tenant, "slug": f"c-{collection.hex[:8]}"},
        )
        await connection.execute(
            text(
                "INSERT INTO knowledge_sources (id, tenant_id, collection_id, name, kind) "
                "VALUES (:id, :tenant, :collection, 'up', 'upload')"
            ),
            {"id": source, "tenant": tenant, "collection": collection},
        )
        await connection.execute(
            text(
                "INSERT INTO documents (id, tenant_id, collection_id, source_id, external_id, "
                "uri, title, mime_type, version_hash, raw_file_id, acl_principals) VALUES "
                "(:id, :tenant, :collection, :source, :external, 'u', 'T', 'text/plain', :hash, "
                ":file, ARRAY[:principal])"
            ),
            {
                "id": knowledge,
                "tenant": tenant,
                "collection": collection,
                "source": source,
                "external": knowledge.hex,
                "hash": digest,
                "file": file_id,
                "principal": f"user:{reader}",
            },
        )
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)}
        )
        await connection.execute(
            text("SELECT set_config('app.user_id', :user, true)"), {"user": str(reader)}
        )
        await connection.execute(text("SET LOCAL ROLE ar_app"))
        shared = await connection.scalar(
            text("SELECT count(*) FROM documents WHERE id = :id"), {"id": document}
        )
        visible = await connection.scalar(
            text("SELECT count(*) FROM documents WHERE id = :id"), {"id": knowledge}
        )
    await engine.dispose()
    assert shared == 0
    assert visible == 1


def _chunk(
    tenant: uuid.UUID,
    collection: uuid.UUID,
    source: uuid.UUID,
    document: uuid.UUID,
    lexical: str,
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=uuid.uuid4(),
        tenant_id=tenant,
        collection_id=collection,
        document_id=document,
        source_id=source,
        index_version=1,
        dense=unit_vector(lexical, 1024),
        lexical_text=lexical,
        acl=["tenant:*"],
        classification="internal",
        title=lexical[:40],
    )


def _query(
    row: IndexedChunk, text_value: str, *, document_ids: tuple[uuid.UUID, ...]
) -> HybridQuery:
    return HybridQuery(
        tenant_id=row.tenant_id,
        text=text_value,
        dense=row.dense,
        targets=[
            SearchTarget(
                collection_id=row.collection_id,
                index_version=1,
                store_collection="pg",
            )
        ],
        principals=["tenant:*"],
        allowed_classifications=["internal"],
        document_ids=document_ids,
    )

"""RetrievalStore conformance for pgvector. Spec: docs/03-specs/10-knowledge.md §10."""

import os
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ar_common.vectors import unit_vector
from ar_domain.knowledge.store import StoreUnavailable
from ar_domain.knowledge.store_pgvector import PgVectorStore
from ar_domain.knowledge.store_types import (
    DeleteFilter,
    HybridQuery,
    IndexedChunk,
    PhysicalCollectionSpec,
    SearchTarget,
)

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


def _alembic(url: str) -> None:
    import subprocess

    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url)
    return url


def _chunk(
    *,
    tenant: uuid.UUID,
    collection: uuid.UUID,
    document: uuid.UUID,
    source: uuid.UUID,
    text_value: str,
    acl: list[str],
    dense: list[float] | None = None,
    version: int = 1,
    classification: str = "internal",
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=uuid.uuid4(),
        tenant_id=tenant,
        collection_id=collection,
        document_id=document,
        source_id=source,
        index_version=version,
        dense=dense or unit_vector(text_value, 1024),
        lexical_text=text_value,
        acl=acl,
        classification=classification,
        title=text_value[:40],
    )


async def _parents(url: str, rows: list[IndexedChunk]) -> None:
    engine = create_async_engine(url)
    plan = uuid.uuid4()
    tenants = {row.tenant_id for row in rows}
    collections = {(row.tenant_id, row.collection_id) for row in rows}
    sources = {(row.tenant_id, row.collection_id, row.source_id) for row in rows}
    documents = {(row.tenant_id, row.collection_id, row.source_id, row.document_id) for row in rows}
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO plans (id, key, name, limits) VALUES (:id, :key, 'Plan', '{}'::jsonb)"
            ),
            {"id": plan, "key": f"plan-{plan.hex[:8]}"},
        )
        await connection.execute(
            text("INSERT INTO tenants (id, slug, name, plan_id) VALUES (:id, :slug, 'T', :plan)"),
            [{"id": tenant, "slug": f"t-{tenant.hex[:10]}", "plan": plan} for tenant in tenants],
        )
        await connection.execute(
            text(
                "INSERT INTO knowledge_collections (id, tenant_id, slug, name, store_collection) "
                "VALUES (:id, :tenant, :slug, 'Lib', 'pg:1024')"
            ),
            [
                {"id": collection, "tenant": tenant, "slug": f"c-{collection.hex[:8]}"}
                for tenant, collection in collections
            ],
        )
        await connection.execute(
            text(
                "INSERT INTO knowledge_sources (id, tenant_id, collection_id, name, kind) "
                "VALUES (:id, :tenant, :collection, 'up', 'upload')"
            ),
            [
                {"id": source, "tenant": tenant, "collection": collection}
                for tenant, collection, source in sources
            ],
        )
        await connection.execute(
            text(
                "INSERT INTO documents (id, tenant_id, collection_id, source_id, external_id, "
                "uri, title, mime_type, version_hash) "
                "VALUES (:id, :tenant, :collection, :source, :external, 'u', 'T', 'text/plain', 'h')"  # noqa: E501
            ),
            [
                {
                    "id": document,
                    "tenant": tenant,
                    "collection": collection,
                    "source": source,
                    "external": document.hex,
                }
                for tenant, collection, source, document in documents
            ],
        )
        await connection.execute(
            text(
                "INSERT INTO document_chunks (id, tenant_id, document_id, ordinal, text, "
                "token_count, index_version) "
                "VALUES (:id, :tenant, :document, 0, :text, 4, :version)"
            ),
            [
                {
                    "id": row.chunk_id,
                    "tenant": row.tenant_id,
                    "document": row.document_id,
                    "text": row.lexical_text,
                    "version": row.index_version,
                }
                for row in rows
            ],
        )
    await engine.dispose()


def _query(
    row: IndexedChunk,
    *,
    text_value: str,
    principals: list[str],
    dense: list[float] | None = None,
    version: int | None = None,
    classifications: list[str] | None = None,
    dense_k: int = 10,
) -> HybridQuery:
    return HybridQuery(
        tenant_id=row.tenant_id,
        text=text_value,
        dense=dense or unit_vector(text_value, 1024),
        targets=[
            SearchTarget(
                collection_id=row.collection_id,
                index_version=row.index_version if version is None else version,
                store_collection="pg:1024",
            )
        ],
        principals=principals,
        allowed_classifications=classifications
        or ["public", "internal", "confidential", "restricted"],
        dense_k=dense_k,
        lexical_k=dense_k,
        fused_k=dense_k,
    )


@pytest.mark.asyncio
async def test_pgvector_conformance(database_url: str) -> None:
    store = PgVectorStore(database_url)
    spec = PhysicalCollectionSpec(
        tenant_id=uuid.uuid4(), collection_id=uuid.uuid4(), model_key="embed", dims=1024
    )
    first = await store.ensure_collection(spec)
    assert first == await store.ensure_collection(spec) == "pg:1024"
    with pytest.raises(Exception, match="unsupported_embedding_dims"):
        await store.ensure_collection(
            PhysicalCollectionSpec(
                tenant_id=spec.tenant_id,
                collection_id=spec.collection_id,
                model_key="embed",
                dims=12,
            )
        )
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    collection = uuid.uuid4()
    source = uuid.uuid4()
    document = uuid.uuid4()
    other_document = uuid.uuid4()
    rare = _chunk(
        tenant=tenant_a,
        collection=collection,
        document=document,
        source=source,
        text_value="badge token ZX-4471",
        acl=["user:ada"],
        dense=unit_vector("unrelated-vector", 1024),
    )
    dense_target = _chunk(
        tenant=tenant_a,
        collection=collection,
        document=other_document,
        source=source,
        text_value="alpha beta gamma",
        acl=["user:ada"],
        dense=unit_vector("cluster-target", 1024),
    )
    other_collection = uuid.uuid4()
    hidden = _chunk(
        tenant=tenant_b,
        collection=other_collection,
        document=uuid.uuid4(),
        source=uuid.uuid4(),
        text_value="badge token ZX-4471",
        acl=["user:ada"],
    )
    restricted = _chunk(
        tenant=tenant_a,
        collection=collection,
        document=uuid.uuid4(),
        source=source,
        text_value="secret restricted note",
        acl=["user:ada"],
        classification="restricted",
    )
    old = _chunk(
        tenant=tenant_a,
        collection=collection,
        document=uuid.uuid4(),
        source=source,
        text_value="old index version",
        acl=["user:ada"],
        version=1,
    )
    current = _chunk(
        tenant=tenant_a,
        collection=collection,
        document=old.document_id,
        source=source,
        text_value="current index version",
        acl=["user:ada"],
        version=2,
    )
    rows = [rare, dense_target, hidden, restricted, old, current]
    await _parents(database_url, rows)
    assert await store.upsert("pg:1024", rows) == len(rows)
    assert await store.upsert("pg:1024", rows) == len(rows)
    assert await store.count("pg:1024", tenant_a, collection, 1) == 4
    ada = _query(rare, text_value="ZX-4471", principals=["user:ada"])
    hits = await store.search(ada)
    assert hits and hits[0].chunk_id == rare.chunk_id
    forged = HybridQuery(
        tenant_id=tenant_a,
        text="ZX-4471",
        dense=unit_vector("ZX-4471", 1024),
        targets=[
            SearchTarget(
                collection_id=other_collection, index_version=1, store_collection="pg:1024"
            )
        ],
        principals=["user:ada"],
        allowed_classifications=["internal"],
    )
    assert all(hit.chunk_id != hidden.chunk_id for hit in await store.search(forged))
    visible = await store.search(
        _query(
            restricted, text_value="secret", principals=["user:ada"], classifications=["internal"]
        )
    )
    assert all(hit.chunk_id != restricted.chunk_id for hit in visible)
    blue = await store.search(
        _query(current, text_value="current index", principals=["user:ada"], version=2)
    )
    assert current.chunk_id in {hit.chunk_id for hit in blue}
    assert old.chunk_id not in {hit.chunk_id for hit in blue}
    dense_hits = await store.search(
        _query(
            dense_target,
            text_value="no-shared-tokens-qqqq",
            principals=["user:ada"],
            dense=list(dense_target.dense),
        )
    )
    assert dense_hits[0].chunk_id == dense_target.chunk_id
    with pytest.raises(ValueError):
        HybridQuery(
            tenant_id=tenant_a,
            text="x",
            dense=[0.0] * 1024,
            targets=[
                SearchTarget(collection_id=collection, index_version=1, store_collection="pg")
            ],
            principals=[],
            allowed_classifications=["internal"],
        )
    await store.set_acl("pg:1024", tenant_a, document, ["user:nobody"], "internal")
    revoked = await store.search(ada)
    assert all(hit.chunk_id != rare.chunk_id for hit in revoked)
    removed = await store.delete(
        "pg:1024",
        DeleteFilter(tenant_id=tenant_a, document_id=other_document),
    )
    assert removed >= 1
    health = await store.health()
    assert health.ok and health.detail.startswith("0.8")
    exported = []
    async for batch in store.export("pg:1024", tenant_a, collection, 2):
        exported.extend(batch)
    assert [item.chunk_id for item in exported] == sorted(item.chunk_id for item in exported)
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text("SET enable_seqscan = off"))
        explained = await connection.execute(
            text(
                "EXPLAIN SELECT chunk_id FROM chunk_embeddings "
                "WHERE dims = 1024 ORDER BY embedding::halfvec(1024) <=> :q LIMIT 5"
            ),
            {"q": "[" + ",".join(["0"] * 1024) + "]"},
        )
        plan = "\n".join(str(row[0]) for row in explained)
    await engine.dispose()
    assert "ix_chunk_emb_hnsw_1024" in plan
    dead = PgVectorStore("postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:1/none")
    started = time.perf_counter()
    with pytest.raises(StoreUnavailable):
        await dead.count("pg:1024", tenant_a, collection, 1)
    assert time.perf_counter() - started < 5


@pytest.mark.asyncio
async def test_filter_runs_before_the_limit(database_url: str) -> None:
    tenant = uuid.uuid4()
    collection = uuid.uuid4()
    source = uuid.uuid4()
    query_dense = unit_vector("needle-vector", 1024)
    readable = [
        _chunk(
            tenant=tenant,
            collection=collection,
            document=uuid.uuid4(),
            source=source,
            text_value=f"readable-{index}",
            acl=["user:ada"],
            dense=query_dense,
        )
        for index in range(25)
    ]
    hidden = [
        _chunk(
            tenant=tenant,
            collection=collection,
            document=uuid.uuid4(),
            source=source,
            text_value=f"hidden-{index}",
            acl=["user:other"],
            dense=query_dense,
        )
        for index in range(40)
    ]
    rows = readable + hidden
    await _parents(database_url, rows)
    store = PgVectorStore(database_url)
    assert await store.upsert("pg:1024", rows) == len(rows)
    hits = await store.search(
        _query(
            readable[0],
            text_value="zzzz-no-lexical",
            principals=["user:ada"],
            dense=query_dense,
            dense_k=10,
        )
    )
    readable_ids = {row.chunk_id for row in readable}
    assert len(hits) == 10
    assert {hit.chunk_id for hit in hits} <= readable_ids

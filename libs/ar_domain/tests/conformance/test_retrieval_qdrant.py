"""RetrievalStore conformance for Qdrant, plus a pgvector parity copy.

Spec: docs/03-specs/10-knowledge.md §8 and §10.
"""

import os
import subprocess
import time
import uuid

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ar_common.vectors import unit_vector
from ar_domain.knowledge.store import StoreUnavailable
from ar_domain.knowledge.store_pgvector import PgVectorStore
from ar_domain.knowledge.store_qdrant import QdrantStore
from ar_domain.knowledge.store_types import (
    DeleteFilter,
    HybridQuery,
    IndexedChunk,
    PhysicalCollectionSpec,
    SearchTarget,
)

pytestmark = pytest.mark.qdrant


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


def _query(
    row: IndexedChunk,
    name: str,
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
                store_collection=name,
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
async def test_qdrant_conformance() -> None:
    store = QdrantStore()
    spec = PhysicalCollectionSpec(
        tenant_id=uuid.uuid4(),
        collection_id=uuid.uuid4(),
        isolation_tier="dedicated",
        model_key="fake-embed",
        dims=1024,
    )
    name = await store.ensure_collection(spec)
    assert name == await store.ensure_collection(spec)
    with pytest.raises(Exception, match="unsupported_embedding_dims"):
        await store.ensure_collection(
            PhysicalCollectionSpec(
                tenant_id=spec.tenant_id,
                collection_id=spec.collection_id,
                model_key="fake-embed",
                dims=12,
            )
        )
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    collection, other_collection = uuid.uuid4(), uuid.uuid4()
    source = uuid.uuid4()
    document, other_document = uuid.uuid4(), uuid.uuid4()
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
    assert await store.upsert(name, rows) == len(rows)
    assert await store.upsert(name, rows) == len(rows)
    assert await store.count(name, tenant_a, collection, 1) == 4
    ada = _query(rare, name, text_value="ZX-4471", principals=["user:ada"])
    hits = await store.search(ada)
    assert hits and hits[0].chunk_id == rare.chunk_id
    forged = _query(hidden, name, text_value="ZX-4471", principals=["user:ada"])
    forged = forged.model_copy(update={"tenant_id": tenant_a})
    assert all(hit.chunk_id != hidden.chunk_id for hit in await store.search(forged))
    visible = await store.search(
        _query(
            restricted,
            name,
            text_value="secret",
            principals=["user:ada"],
            classifications=["internal"],
        )
    )
    assert all(hit.chunk_id != restricted.chunk_id for hit in visible)
    blue = await store.search(
        _query(current, name, text_value="current index", principals=["user:ada"], version=2)
    )
    assert current.chunk_id in {hit.chunk_id for hit in blue}
    assert old.chunk_id not in {hit.chunk_id for hit in blue}
    dense_hits = await store.search(
        _query(
            dense_target,
            name,
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
                SearchTarget(collection_id=collection, index_version=1, store_collection=name)
            ],
            principals=[],
            allowed_classifications=["internal"],
        )
    await store.set_acl(name, tenant_a, document, ["user:nobody"], "internal")
    assert all(hit.chunk_id != rare.chunk_id for hit in await store.search(ada))
    assert (
        await store.delete(name, DeleteFilter(tenant_id=tenant_a, document_id=other_document)) >= 1
    )
    health = await store.health()
    assert health.ok
    exported = []
    async for batch in store.export(name, tenant_a, collection, 2):
        exported.extend(batch)
    assert [item.chunk_id for item in exported] == sorted(item.chunk_id for item in exported)
    query_dense = unit_vector("needle-vector", 1024)
    readable = [
        _chunk(
            tenant=tenant_a,
            collection=collection,
            document=uuid.uuid4(),
            source=source,
            text_value=f"readable-{index}",
            acl=["user:ada"],
            dense=query_dense,
        )
        for index in range(15)
    ]
    concealed = [
        _chunk(
            tenant=tenant_a,
            collection=collection,
            document=uuid.uuid4(),
            source=source,
            text_value=f"hidden-{index}",
            acl=["user:other"],
            dense=query_dense,
        )
        for index in range(20)
    ]
    await store.upsert(name, readable + concealed)
    limited = await store.search(
        _query(
            readable[0],
            name,
            text_value="zzzz-no-lexical",
            principals=["user:ada"],
            dense=query_dense,
            dense_k=10,
        )
    )
    readable_ids = {row.chunk_id for row in readable}
    assert len(limited) == 10
    assert {hit.chunk_id for hit in limited} <= readable_ids
    extra = [
        _chunk(
            tenant=tenant_a,
            collection=collection,
            document=uuid.uuid4(),
            source=source,
            text_value=f"batch-{index}",
            acl=["user:ada"],
        )
        for index in range(520)
    ]
    assert await store.upsert(name, extra) == 520
    dead = QdrantStore(client=QdrantClient(url="http://127.0.0.1:1", timeout=2))
    started = time.perf_counter()
    with pytest.raises(StoreUnavailable):
        await dead.count(name, tenant_a, collection, 1)
    assert time.perf_counter() - started < 5


def _alembic(url: str) -> None:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
        env=env,
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
                "VALUES (:id, :tenant, :collection, :source, :external, 'u', 'T', "
                "'text/plain', 'h')"
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


@pytest.mark.asyncio
async def test_pgvector_qdrant_round_trip_keeps_the_same_citation() -> None:
    database_url = os.environ["AR_DATABASE_URL"]
    _alembic(database_url)
    pg = PgVectorStore(database_url)
    qdrant = QdrantStore()
    tenant, collection, document, source = (uuid.uuid4() for _ in range(4))
    spec = PhysicalCollectionSpec(
        tenant_id=tenant,
        collection_id=collection,
        isolation_tier="dedicated",
        model_key="roundtrip",
        dims=1024,
    )
    qname = await qdrant.ensure_collection(spec)
    await pg.ensure_collection(spec)
    text_value = "Visitor desk token ZX-4471"
    row = _chunk(
        tenant=tenant,
        collection=collection,
        document=document,
        source=source,
        text_value=text_value,
        acl=["user:ada"],
        dense=unit_vector("round-trip-vector", 1024),
    )
    await _parents(database_url, [row])
    assert await pg.upsert("pg:1024", [row]) == 1
    exported = []
    async for batch in pg.export("pg:1024", tenant, collection, 1):
        exported.extend(batch)
    copied = row.model_copy(update={"dense": exported[0].dense})
    assert await qdrant.upsert(qname, [copied]) == 1
    pg_hits = await pg.search(_query(row, "pg:1024", text_value="ZX-4471", principals=["user:ada"]))
    q_hits = await qdrant.search(_query(row, qname, text_value="ZX-4471", principals=["user:ada"]))
    assert pg_hits[0].chunk_id == q_hits[0].chunk_id == row.chunk_id
    back = []
    async for batch in qdrant.export(qname, tenant, collection, 1):
        back.extend(batch)
    assert back[0].chunk_id == exported[0].chunk_id
    assert await pg.count("pg:1024", tenant, collection, 1) == await qdrant.count(
        qname, tenant, collection, 1
    )

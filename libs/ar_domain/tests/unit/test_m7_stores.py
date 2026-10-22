"""Adapter method coverage for pgvector and qdrant. Spec: docs/03-specs/10-knowledge.md."""

import asyncio
import uuid
from types import SimpleNamespace

import httpx
import pytest
import respx

from ar_domain.chat.service import ChatService
from ar_domain.knowledge.store import StoreError, StoreUnavailable, get_retrieval_store
from ar_domain.knowledge.store_pgvector import (
    PgVectorStore,
    _as_floats,
    _chunk_params,
    _delete_clause,
    _version_ok,
)
from ar_domain.knowledge.store_qdrant import QdrantStore, _models, _sparse
from ar_domain.knowledge.store_types import (
    DeleteFilter,
    HybridQuery,
    IndexedChunk,
    PhysicalCollectionSpec,
    SearchTarget,
)
from ar_ingest.activities import (
    acl_sync_activity,
    audit_activity,
    bind_store,
    delete_document_activity,
    migrate_activity,
    reindex_activity,
    sync_source_activity,
)

pytestmark = pytest.mark.unit


def _ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _chunk(dense: list[float] | None = None) -> IndexedChunk:
    tenant, collection, document, source, chunk = _ids()
    return IndexedChunk(
        chunk_id=chunk,
        tenant_id=tenant,
        collection_id=collection,
        document_id=document,
        source_id=source,
        index_version=1,
        dense=dense or [0.1] * 1024,
        lexical_text="visitor desk ZX-4471",
        acl=["tenant:*"],
        classification="internal",
        title="Visitor guide",
    )


class _Result:
    def __init__(self, rows: list[dict[str, object]] | None = None, rowcount: int = 1) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _Session:
    def __init__(self, script: list[object]) -> None:
        self.script = script

    def begin(self) -> _Session:
        return self

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, statement: object, _params: object = None) -> _Result:
        sql = str(statement)
        if "SET LOCAL" in sql:
            return _Result()
        item = self.script.pop(0) if self.script else _Result()
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, _Result)
        return item

    async def close(self) -> None:
        return None


def _store(script: list[object]) -> PgVectorStore:
    session = _Session(script)
    store = PgVectorStore(dsn="postgresql+asyncpg://example")
    store._session_factory = lambda: session  # type: ignore[method-assign,assignment]
    store._read_factory = lambda: session  # type: ignore[method-assign,assignment]
    return store


def _query(chunk: IndexedChunk) -> HybridQuery:
    return HybridQuery(
        tenant_id=chunk.tenant_id,
        text="visitor",
        dense=chunk.dense,
        targets=[
            SearchTarget(
                collection_id=chunk.collection_id,
                index_version=1,
                store_collection="pg:1024",
            )
        ],
        principals=["tenant:*"],
        allowed_classifications=["internal"],
    )


def test_pgvector_methods_use_the_bound_session() -> None:
    chunk = _chunk()
    hit = {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "collection_id": chunk.collection_id,
        "score": 0.5,
        "dense_rank": 1,
        "lexical_rank": None,
    }
    store = _store(
        [
            _Result(rowcount=1),
            _Result(rowcount=1),
            _Result(rowcount=2),
            _Result([hit]),
            _Result([{"count": 3}]),
            _Result(
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "index_version": 1,
                        "embedding": "[0.1,0.2]",
                    }
                ]
            ),
            _Result([]),
            _Result([{"extversion": "0.8.7"}]),
        ]
    )
    spec = PhysicalCollectionSpec(
        tenant_id=chunk.tenant_id,
        collection_id=chunk.collection_id,
        model_key="fake-embed",
        dims=1024,
    )
    assert asyncio.run(store.ensure_collection(spec)) == "pg:1024"
    assert asyncio.run(store.upsert("pg:1024", [chunk])) == 1
    selector = DeleteFilter(
        tenant_id=chunk.tenant_id,
        collection_id=chunk.collection_id,
        document_id=chunk.document_id,
        index_version=1,
        index_version_ne=2,
        chunk_ids=[chunk.chunk_id],
    )
    assert asyncio.run(store.delete("pg:1024", selector)) == 1
    assert (
        asyncio.run(store.set_acl("pg:1024", chunk.tenant_id, chunk.document_id, [], "public")) == 2
    )
    found = asyncio.run(store.search(_query(chunk)))
    assert found[0].chunk_id == chunk.chunk_id
    assert found[0].lexical_rank is None
    assert asyncio.run(store.count("pg:1024", chunk.tenant_id, chunk.collection_id, 1)) == 3
    exported = []

    async def _drain() -> None:
        async for batch in store.export("pg:1024", chunk.tenant_id, chunk.collection_id, 1, 1):
            exported.extend(batch)

    asyncio.run(_drain())
    assert exported[0].dense == [0.1, 0.2]
    health = asyncio.run(store.health())
    assert health.ok
    assert health.detail == "0.8.7"
    params = _chunk_params(chunk.model_copy(update={"text_search_config": "missing"}))
    assert params["text_search_config"] == "simple"
    assert _as_floats([1, 2]) == [1.0, 2.0]
    assert _as_floats("[]") == []
    assert not _version_ok("nope")
    assert not _version_ok("0.7.0")
    with pytest.raises(StoreError):
        _delete_clause(DeleteFilter.model_construct(tenant_id=chunk.tenant_id))


def test_pgvector_failures_are_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk = _chunk()
    broken = _store([RuntimeError("down")])
    with pytest.raises(StoreUnavailable):
        asyncio.run(broken.upsert("pg:1024", [chunk]))
    searching = _store([RuntimeError("down")])
    with pytest.raises(StoreUnavailable):
        asyncio.run(searching.search(_query(chunk)))
    missing = PgVectorStore()
    health = asyncio.run(missing.health())
    assert not health.ok
    short = _chunk(dense=[0.1, 0.2])
    with pytest.raises(Exception):
        asyncio.run(_store([]).upsert("pg:1024", [short]))
    bad = PhysicalCollectionSpec(
        tenant_id=chunk.tenant_id,
        collection_id=chunk.collection_id,
        model_key="fake-embed",
        dims=12,
    )
    with pytest.raises(Exception):
        asyncio.run(PgVectorStore().ensure_collection(bad))
    own = _Session([_Result(rowcount=4)])
    assert asyncio.run(_store([]).upsert("pg:1024", [chunk], session=own)) == 1  # type: ignore[arg-type]
    assert own.script == []
    monkeypatch.setenv("AR_VECTOR_PG_READ_DSN", "postgresql+asyncpg://read")
    created: list[str] = []

    def engine(dsn: str, **_kwargs: object) -> object:
        created.append(dsn)
        return object()

    session = _Session([_Result([{"extversion": "0.8.0"}])])
    monkeypatch.setattr(
        "ar_domain.knowledge.store_pgvector.create_async_engine",
        engine,
    )
    monkeypatch.setattr(
        "ar_domain.knowledge.store_pgvector.async_sessionmaker",
        lambda *_args, **_kwargs: lambda: session,
    )
    wired = PgVectorStore(dsn="postgresql+asyncpg://write")
    assert asyncio.run(wired.health()).ok
    assert asyncio.run(wired.search(_query(chunk))) == []
    assert (
        asyncio.run(wired.drop_collection("pg:1024", chunk.tenant_id, chunk.collection_id)) is None
    )
    assert created


class _Models:
    class PointStruct:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    class SparseVector:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    class VectorParams:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    class SparseVectorParams:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    class Filter:
        @staticmethod
        def model_validate(payload: dict[str, object]) -> dict[str, object]:
            return payload

    Distance = SimpleNamespace(COSINE="Cosine")


class _Client:
    def __init__(self) -> None:
        self.created = False
        self.points: list[object] = []
        self.scrolls = 0

    def get_collections(self) -> SimpleNamespace:
        name = "ar_kn_fake_embed_1024" if self.created else "other"
        return SimpleNamespace(collections=[SimpleNamespace(name=name)])

    def create_collection(self, **_kwargs: object) -> None:
        self.created = True

    def create_payload_index(self, **_kwargs: object) -> None:
        return None

    def upsert(self, **kwargs: object) -> None:
        points = kwargs["points"]
        assert isinstance(points, list)
        self.points.extend(points)

    def delete(self, **_kwargs: object) -> None:
        return None

    def set_payload(self, **_kwargs: object) -> None:
        return None

    def count(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(count=1)

    def query_points(self, **_kwargs: object) -> SimpleNamespace:
        chunk = self.points[0]
        payload = chunk.payload  # type: ignore[attr-defined]
        hit = SimpleNamespace(id=payload["chunk_id"], payload=payload)
        return SimpleNamespace(points=[hit])

    def scroll(self, **_kwargs: object) -> tuple[list[object], object]:
        self.scrolls += 1
        if self.scrolls > 1:
            return [], None
        chunk = self.points[0]
        payload = dict(chunk.payload)  # type: ignore[attr-defined]
        point = SimpleNamespace(payload=payload, vector={"dense": [0.1, 0.2]})
        return [point], "next"


def test_qdrant_methods_against_a_fake_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    monkeypatch.setattr("ar_domain.knowledge.store_qdrant._models", lambda: _Models)
    client = _Client()
    store = QdrantStore(client=client)
    chunk = _chunk()
    spec = PhysicalCollectionSpec(
        tenant_id=chunk.tenant_id,
        collection_id=chunk.collection_id,
        model_key="fake-embed",
        dims=1024,
    )
    name = asyncio.run(store.ensure_collection(spec))
    assert name.startswith("ar_kn_")
    asyncio.run(store.ensure_collection(spec))
    assert asyncio.run(store.upsert(name, [chunk])) == 1
    found = asyncio.run(store.search(_query(chunk)))
    assert found[0].document_id == chunk.document_id
    assert asyncio.run(store.count(name, chunk.tenant_id, chunk.collection_id, 1)) == 1
    assert (
        asyncio.run(store.set_acl(name, chunk.tenant_id, chunk.document_id, ["user:a"], "public"))
        == 1
    )
    selector = DeleteFilter(
        tenant_id=chunk.tenant_id, document_id=chunk.document_id, chunk_ids=[chunk.chunk_id]
    )
    assert asyncio.run(store.delete(name, selector)) == 1
    asyncio.run(store.drop_collection(name, chunk.tenant_id, chunk.collection_id))
    exported = []

    async def _drain() -> None:
        async for batch in store.export(
            name, chunk.tenant_id, chunk.collection_id, 1, batch_size=1
        ):
            exported.extend(batch)

    asyncio.run(_drain())
    assert exported[0].dense == [0.1, 0.2]
    with pytest.raises(Exception):
        asyncio.run(store.upsert(name, [_chunk(dense=[0.2])]))
    bare = HybridQuery.model_construct(
        tenant_id=chunk.tenant_id,
        text="x",
        dense=chunk.dense,
        targets=[],
        principals=[],
        allowed_classifications=[],
        dense_k=1,
        lexical_k=1,
        fused_k=1,
        rrf_k=60,
    )
    with pytest.raises(ValueError):
        asyncio.run(store.search(bare))
    only_tenant = DeleteFilter.model_construct(
        tenant_id=chunk.tenant_id,
        collection_id=None,
        document_id=None,
        index_version=None,
        index_version_ne=None,
        chunk_ids=[],
    )
    with pytest.raises(ValueError):
        asyncio.run(store.delete(name, only_tenant))
    monkeypatch.delenv("AR_QDRANT_URL", raising=False)
    assert not asyncio.run(store.health()).ok
    monkeypatch.setenv("AR_QDRANT_URL", "http://qdrant.test")
    with respx.mock:
        respx.get("http://qdrant.test/readyz").mock(return_value=httpx.Response(200, text="ok"))
        assert asyncio.run(store.health()).ok
        respx.get("http://qdrant.test/readyz").mock(return_value=httpx.Response(503))
        with pytest.raises(StoreUnavailable):
            asyncio.run(store.health())
    monkeypatch.setenv("AR_FASTEMBED_CACHE_DIR", str(tmp_path))
    indices, values = _sparse("ZX-4471 rare")
    assert indices and values
    with pytest.raises(StoreError):
        get_retrieval_store("missing")
    monkeypatch.delenv("AR_QDRANT_URL", raising=False)
    with pytest.raises(StoreError):
        get_retrieval_store("qdrant")

    class _Down:
        def count(self, **_kwargs: object) -> None:
            raise RuntimeError("down")

    down = QdrantStore(client=_Down())
    with pytest.raises(StoreUnavailable):
        asyncio.run(down.count("missing", chunk.tenant_id, chunk.collection_id, 1))
    try:
        _models()
    except StoreError:
        pass


def test_migrate_and_sync_activities_record_the_switch() -> None:
    store = ChatService()
    collection_id = uuid.uuid4()
    source_id = uuid.uuid4()
    document_id = uuid.uuid4()
    tenant = uuid.uuid4()
    store.knowledge_collections[collection_id] = {
        "id": collection_id,
        "tenant_id": tenant,
        "store_backend": "pgvector",
        "index_version": 1,
    }
    store.knowledge_sources[source_id] = {
        "id": source_id,
        "tenant_id": tenant,
        "collection_id": collection_id,
        "kind": "upload",
        "status": "idle",
        "config": {"items": []},
    }
    store.knowledge_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "collection_id": collection_id,
        "source_id": source_id,
        "status": "indexed",
    }
    bind_store(store)
    dry = asyncio.run(
        migrate_activity(
            {"collection_id": str(collection_id), "target_backend": "qdrant", "dry_run": True}
        )
    )
    assert dry["status"] == "dry_run"
    switched = asyncio.run(
        migrate_activity({"collection_id": str(collection_id), "target_backend": "qdrant"})
    )
    assert switched["switched"] is True
    failed = asyncio.run(
        migrate_activity(
            {
                "collection_id": str(collection_id),
                "target_backend": "pgvector",
                "fail_verification": True,
            }
        )
    )
    assert failed["switched"] is False
    rolled = asyncio.run(
        migrate_activity(
            {"collection_id": str(collection_id), "target_backend": "pgvector", "rollback": True}
        )
    )
    assert rolled["status"] == "rolled_back"
    audited = asyncio.run(audit_activity({"collection_id": str(collection_id)}))
    assert audited["drift"] == 0
    synced = asyncio.run(sync_source_activity({"source_id": str(source_id), "mode": "full"}))
    assert synced["status"]
    acl = asyncio.run(acl_sync_activity({"source_id": str(source_id)}))
    assert acl["status"]
    reindexed = asyncio.run(
        reindex_activity({"collection_id": str(collection_id), "embedding_alias": "fake-embed"})
    )
    assert reindexed["job_id"]
    deleted = asyncio.run(delete_document_activity({"document_id": str(document_id)}))
    assert deleted["status"] == "deleted"
    with pytest.raises(Exception):
        asyncio.run(sync_source_activity({"source_id": str(uuid.uuid4())}))

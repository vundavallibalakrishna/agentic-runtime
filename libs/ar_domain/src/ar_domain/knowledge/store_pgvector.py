"""pgvector RetrievalStore adapter. Spec: docs/03-specs/10-knowledge.md §7."""

import os
import time
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ar_domain.knowledge.store import StoreError, StoreUnavailable, UnsupportedDims
from ar_domain.knowledge.store_types import (
    SUPPORTED_DIMS,
    TEXT_CONFIGS,
    ExportedVector,
    HybridQuery,
    IndexedChunk,
    PhysicalCollectionSpec,
    ScoredChunk,
    StoreCapabilities,
    StoreHealth,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from ar_domain.knowledge.store_types import DeleteFilter


class PgVectorStore:
    """Hybrid search in ``chunk_embeddings``. Writes join the caller's session."""

    backend: ClassVar[str] = "pgvector"
    capabilities: ClassVar[StoreCapabilities] = StoreCapabilities(
        native_sparse=False,
        transactional_with_pg=True,
        supported_dims=SUPPORTED_DIMS,
    )

    def __init__(self, dsn: str = "") -> None:
        self.dsn = dsn
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._read_factory: async_sessionmaker[AsyncSession] | None = None

    def bind(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = factory

    async def ensure_collection(self, spec: PhysicalCollectionSpec) -> str:
        if spec.dims not in SUPPORTED_DIMS:
            raise UnsupportedDims(f"unsupported_embedding_dims:{spec.dims}")
        return f"pg:{spec.dims}"

    async def drop_collection(
        self, store_collection: str, tenant_id: object, collection_id: object
    ) -> None:
        del store_collection
        await self._exec(
            "DELETE FROM chunk_embeddings "
            "WHERE tenant_id = :tenant AND collection_id = :collection",
            {"tenant": tenant_id, "collection": collection_id},
        )

    async def upsert(
        self,
        store_collection: str,
        chunks: Sequence[IndexedChunk],
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del store_collection
        written = 0
        for start in range(0, len(chunks), 512):
            batch = chunks[start : start + 512]
            params = []
            for chunk in batch:
                if len(chunk.dense) not in SUPPORTED_DIMS:
                    raise UnsupportedDims("unsupported_embedding_dims")
                params.append(_chunk_params(chunk))
            await self._exec(_UPSERT_SQL, params, session=session)
            written += len(params)
        return written

    async def delete(
        self,
        store_collection: str,
        selector: DeleteFilter,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del store_collection
        clause, params = _delete_clause(selector)
        statement = f"DELETE FROM chunk_embeddings WHERE {clause}"  # noqa: S608
        result = await self._exec(statement, params, session=session)
        return int(result)

    async def set_acl(
        self,
        store_collection: str,
        tenant_id: object,
        document_id: object,
        acl: Sequence[str],
        classification: str,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del store_collection
        result = await self._exec(
            """
            UPDATE chunk_embeddings
            SET acl = :acl, classification = :classification
            WHERE tenant_id = :tenant_id AND document_id = :document_id
            """,
            {
                "acl": list(acl),
                "classification": classification,
                "tenant_id": tenant_id,
                "document_id": document_id,
            },
            session=session,
        )
        return int(result)

    async def search(self, query: HybridQuery) -> list[ScoredChunk]:
        if not query.principals or not query.allowed_classifications:
            raise ValueError("principals and classifications are required")
        dims = len(query.dense)
        configs = list(dict.fromkeys(target.text_search_config for target in query.targets))
        sql = build_hybrid_sql(dims=dims, configs=configs)
        params = {
            "collection_ids": [target.collection_id for target in query.targets],
            "index_versions": [target.index_version for target in query.targets],
            "tenant_id": query.tenant_id,
            "principals": query.principals,
            "allowed": query.allowed_classifications,
            "q": _vector_literal(query.dense),
            "text": query.text,
            "dense_k": query.dense_k,
            "lexical_k": query.lexical_k,
            "fused_k": query.fused_k,
            "rrf_k": query.rrf_k,
        }
        return await self._search(sql, params)

    async def count(
        self, store_collection: str, tenant_id: object, collection_id: object, index_version: int
    ) -> int:
        del store_collection
        value = await self._scalar(
            """
            SELECT count(*) FROM chunk_embeddings
            WHERE tenant_id = :tenant AND collection_id = :collection AND index_version = :version
            """,
            {"tenant": tenant_id, "collection": collection_id, "version": index_version},
        )
        return int(value or 0)  # type: ignore[call-overload,no-any-return]

    async def export(
        self,
        store_collection: str,
        tenant_id: object,
        collection_id: object,
        index_version: int,
        batch_size: int = 512,
    ) -> AsyncIterator[list[ExportedVector]]:
        del store_collection
        offset = 0
        while True:
            fetched = await self._mappings(
                """
                SELECT chunk_id, document_id, index_version, embedding
                FROM chunk_embeddings
                WHERE tenant_id = :tenant AND collection_id = :collection
                  AND index_version = :version
                ORDER BY chunk_id
                LIMIT :limit OFFSET :offset
                """,
                {
                    "tenant": tenant_id,
                    "collection": collection_id,
                    "version": index_version,
                    "limit": batch_size,
                    "offset": offset,
                },
            )
            if not fetched:
                return
            yield [
                ExportedVector(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    index_version=int(row["index_version"]),  # type: ignore[call-overload]
                    dense=_as_floats(row["embedding"]),
                )
                for row in fetched
            ]
            if len(fetched) < batch_size:
                return
            offset += batch_size

    async def health(self) -> StoreHealth:
        started = time.perf_counter()
        try:
            version = await self._scalar(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'", {}
            )
        except StoreUnavailable as exc:
            return StoreHealth(backend="pgvector", ok=False, latency_ms=0, detail=str(exc))
        elapsed = (time.perf_counter() - started) * 1000
        ok = _version_ok(str(version or "0"))
        return StoreHealth(
            backend="pgvector",
            ok=ok,
            latency_ms=elapsed,
            detail=str(version or "missing"),
        )

    async def _search(self, sql: str, params: dict[str, object]) -> list[ScoredChunk]:
        ef = int(os.environ.get("AR_VECTOR_PG_EF_SEARCH", "100"))
        preamble = search_preamble(ef)
        session = await self._connect(read=True)
        try:
            async with session.begin():
                for statement in preamble:
                    await session.execute(text(statement))
                result = await session.execute(text(sql), params)
                mappings = result.mappings().all()
        except Exception as exc:
            raise StoreUnavailable("pgvector search failed") from exc
        finally:
            await session.close()
        return [
            ScoredChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                collection_id=row["collection_id"],
                score=float(row["score"]),
                dense_rank=None if row["dense_rank"] is None else int(row["dense_rank"]),
                lexical_rank=None if row["lexical_rank"] is None else int(row["lexical_rank"]),
            )
            for row in mappings
        ]

    async def _exec(
        self,
        sql: str,
        params: dict[str, object] | list[dict[str, object]],
        *,
        session: AsyncSession | None = None,
    ) -> int:
        if session is not None:
            result = await session.execute(text(sql), params)
            return int(result.rowcount or 0)  # type: ignore[attr-defined]
        own = await self._connect(read=False)
        try:
            async with own.begin():
                result = await own.execute(text(sql), params)
                return int(result.rowcount or 0)  # type: ignore[attr-defined]
        except Exception as exc:
            raise StoreUnavailable("pgvector write failed") from exc
        finally:
            await own.close()

    async def _scalar(self, sql: str, params: dict[str, object]) -> object:
        rows = await self._mappings(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    async def _mappings(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
        session = await self._connect(read=False)
        try:
            async with session.begin():
                result = await session.execute(text(sql), params)
                return [dict(row) for row in result.mappings().all()]
        except Exception as exc:
            raise StoreUnavailable("pgvector read failed") from exc
        finally:
            await session.close()

    async def _connect(self, *, read: bool) -> AsyncSession:
        if not read and self._session_factory is not None:
            return self._session_factory()
        if read and self._read_factory is not None:
            return self._read_factory()
        dsn = os.environ.get("AR_VECTOR_PG_READ_DSN", "").strip() if read else ""
        dsn = dsn or self.dsn
        if not dsn:
            raise StoreUnavailable("pgvector dsn is not configured")
        engine = create_async_engine(dsn, pool_pre_ping=True, connect_args={"timeout": 2})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        if read and os.environ.get("AR_VECTOR_PG_READ_DSN", "").strip():
            self._read_factory = factory
        else:
            self._session_factory = factory
            if read:
                self._read_factory = factory
        return factory()


def build_hybrid_sql(*, dims: int, configs: list[str]) -> str:
    """One hybrid statement. Dims come from the allowlist. Both branches filter."""
    if dims not in SUPPORTED_DIMS:
        raise UnsupportedDims(f"unsupported_embedding_dims:{dims}")
    chosen = [cfg for cfg in configs if cfg in TEXT_CONFIGS]
    if not chosen:
        chosen = ["simple"]
    tsquery = " || ".join(f"websearch_to_tsquery('{cfg}', :text)" for cfg in chosen)
    return _HYBRID_SQL.replace("__DIMS__", str(dims)).replace("__TSQUERY__", tsquery)


_HYBRID_SQL = """
WITH targets(collection_id, index_version) AS (
  SELECT * FROM unnest(CAST(:collection_ids AS uuid[]), CAST(:index_versions AS int[]))
), dense AS (
  SELECT chunk_id, row_number() OVER () AS rank FROM (
    SELECT ce.chunk_id FROM chunk_embeddings ce
    JOIN targets t USING (collection_id, index_version)
    WHERE ce.dims = __DIMS__ AND ce.tenant_id = :tenant_id
      AND ce.acl && CAST(:principals AS text[])
      AND ce.classification = ANY(CAST(:allowed AS text[]))
    ORDER BY ce.embedding::halfvec(__DIMS__) <=> CAST(:q AS halfvec(__DIMS__))
    LIMIT :dense_k) d
), lexical AS (
  SELECT chunk_id, row_number() OVER (ORDER BY score DESC, chunk_id) AS rank FROM (
    SELECT ce.chunk_id, ts_rank_cd(ce.tsv, qq.query, 32) AS score
    FROM chunk_embeddings ce
    JOIN targets t USING (collection_id, index_version),
         (SELECT (__TSQUERY__) AS query) qq
    WHERE ce.tsv @@ qq.query AND ce.tenant_id = :tenant_id
      AND ce.acl && CAST(:principals AS text[])
      AND ce.classification = ANY(CAST(:allowed AS text[]))
    ORDER BY score DESC, ce.chunk_id
    LIMIT :lexical_k) l
)
SELECT ce.chunk_id, ce.document_id, ce.collection_id,
       COALESCE(1.0 / (:rrf_k + d.rank), 0) + COALESCE(1.0 / (:rrf_k + l.rank), 0) AS score,
       d.rank AS dense_rank, l.rank AS lexical_rank
FROM dense d
FULL JOIN lexical l USING (chunk_id)
JOIN chunk_embeddings ce USING (chunk_id)
ORDER BY score DESC, ce.chunk_id
LIMIT :fused_k
"""


_UPSERT_SQL = """
INSERT INTO chunk_embeddings (
  chunk_id, tenant_id, collection_id, document_id, source_id,
  index_version, acl, classification, dims, embedding,
  text_search_config, lexical_text
) VALUES (
  :chunk_id, :tenant_id, :collection_id, :document_id, :source_id,
  :index_version, :acl, :classification, :dims, :embedding,
  :text_search_config, :lexical_text
)
ON CONFLICT (chunk_id) DO UPDATE SET
  acl = EXCLUDED.acl,
  classification = EXCLUDED.classification,
  index_version = EXCLUDED.index_version,
  embedding = EXCLUDED.embedding,
  lexical_text = EXCLUDED.lexical_text,
  dims = EXCLUDED.dims
"""


def search_preamble(ef_search: int) -> list[str]:
    """Session settings that make the dense branch use iterative HNSW scan."""
    safe = ef_search if ef_search > 0 else 100
    return [
        f"SET LOCAL hnsw.ef_search = {safe}",
        "SET LOCAL hnsw.iterative_scan = relaxed_order",
        "SET LOCAL hnsw.max_scan_tuples = 20000",
    ]


def _chunk_params(chunk: IndexedChunk) -> dict[str, object]:
    config = chunk.text_search_config if chunk.text_search_config in TEXT_CONFIGS else "simple"
    return {
        "chunk_id": chunk.chunk_id,
        "tenant_id": chunk.tenant_id,
        "collection_id": chunk.collection_id,
        "document_id": chunk.document_id,
        "source_id": chunk.source_id,
        "index_version": chunk.index_version,
        "acl": list(chunk.acl),
        "classification": chunk.classification,
        "dims": len(chunk.dense),
        "embedding": _vector_literal(chunk.dense),
        "text_search_config": config,
        "lexical_text": chunk.lexical_text,
    }


def _delete_clause(selector: DeleteFilter) -> tuple[str, dict[str, object]]:
    parts = ["tenant_id = :tenant_id"]
    params: dict[str, object] = {"tenant_id": selector.tenant_id}
    if selector.collection_id is not None:
        parts.append("collection_id = :collection_id")
        params["collection_id"] = selector.collection_id
    if selector.document_id is not None:
        parts.append("document_id = :document_id")
        params["document_id"] = selector.document_id
    if selector.index_version is not None:
        parts.append("index_version = :index_version")
        params["index_version"] = selector.index_version
    if selector.index_version_ne is not None:
        parts.append("index_version <> :index_version_ne")
        params["index_version_ne"] = selector.index_version_ne
    if selector.chunk_ids:
        parts.append("chunk_id = ANY(CAST(:chunk_ids AS uuid[]))")
        params["chunk_ids"] = list(selector.chunk_ids)
    if len(parts) == 1:
        raise StoreError("delete filter needs a selector")
    return " AND ".join(parts), params


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _as_floats(value: object) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    text_value = str(value).strip("[]")
    if not text_value:
        return []
    return [float(item) for item in text_value.split(",") if item]


def _version_ok(raw: str) -> bool:
    parts = raw.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return False
    return (major, minor) >= (0, 8)

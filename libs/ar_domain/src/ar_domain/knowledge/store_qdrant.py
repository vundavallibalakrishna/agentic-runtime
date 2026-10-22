"""Qdrant RetrievalStore adapter. Spec: docs/03-specs/10-knowledge.md §8."""

import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import httpx

from ar_domain.knowledge.qdrant_filter import build_filter, hashed_sparse, physical_name
from ar_domain.knowledge.store import StoreError, StoreUnavailable, UnsupportedDims, rrf_fuse
from ar_domain.knowledge.store_types import (
    SUPPORTED_DIMS,
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

    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.knowledge.store_types import DeleteFilter


def _client() -> object:
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
    except ImportError as exc:
        raise StoreError("adapter not installed") from exc
    url = os.environ.get("AR_QDRANT_URL", "").strip()
    if not url:
        raise StoreError("adapter not installed")
    key = os.environ.get("AR_QDRANT_API_KEY", "").strip() or None
    return QdrantClient(url=url, api_key=key, timeout=5)


def _models() -> object:
    """Qdrant model types. Tests replace this when the extra is not installed."""
    try:
        from qdrant_client import models  # noqa: PLC0415
    except ImportError as exc:
        raise StoreError("adapter not installed") from exc
    return models


class QdrantStore:
    """Named dense and sparse vectors. Fusion stays in this process."""

    backend: ClassVar[str] = "qdrant"
    capabilities: ClassVar[StoreCapabilities] = StoreCapabilities(
        native_sparse=True,
        transactional_with_pg=False,
        supported_dims=SUPPORTED_DIMS,
    )

    def __init__(self, client: object | None = None) -> None:
        self._client = client if client is not None else _client()

    async def ensure_collection(self, spec: PhysicalCollectionSpec) -> str:
        if spec.dims not in SUPPORTED_DIMS:
            raise UnsupportedDims("unsupported_embedding_dims")
        name = physical_name(
            isolation_tier=spec.isolation_tier,
            tenant_short=str(spec.tenant_id),
            model_key=spec.model_key,
            dims=spec.dims,
        )
        models = _models()
        listed = self._invoke("get_collections")
        existing = {item.name for item in listed.collections}  # type: ignore[attr-defined]
        if name not in existing:
            self._invoke(
                "create_collection",
                collection_name=name,
                vectors_config={
                    "dense": models.VectorParams(size=spec.dims, distance=models.Distance.COSINE)  # type: ignore[attr-defined]
                },
                sparse_vectors_config={"lexical": models.SparseVectorParams()},  # type: ignore[attr-defined]
            )
            for field in ("tenant_id", "collection_id", "index_version", "document_id"):
                self._invoke(
                    "create_payload_index",
                    collection_name=name,
                    field_name=field,
                    field_schema="keyword" if field != "index_version" else "integer",
                )
        return name

    async def drop_collection(
        self, store_collection: str, tenant_id: object, collection_id: object
    ) -> None:
        self._delete(
            store_collection,
            {"must": [{"key": "collection_id", "match": {"value": str(collection_id)}}]},
            tenant_id,
        )

    async def upsert(
        self,
        store_collection: str,
        chunks: Sequence[IndexedChunk],
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del session
        models = _models()
        points = []
        for chunk in chunks:
            if len(chunk.dense) not in SUPPORTED_DIMS:
                raise UnsupportedDims("unsupported_embedding_dims")
            indices, values = _sparse(chunk.lexical_text)
            points.append(
                models.PointStruct(  # type: ignore[attr-defined]
                    id=str(chunk.chunk_id),
                    vector={
                        "dense": list(chunk.dense),
                        "lexical": models.SparseVector(indices=indices, values=values),  # type: ignore[attr-defined]
                    },
                    payload=_payload(chunk),
                )
            )
        written = 0
        for start in range(0, len(points), 512):
            self._invoke(
                "upsert", collection_name=store_collection, points=points[start : start + 512]
            )
            written += len(points[start : start + 512])
        return written

    async def delete(
        self,
        store_collection: str,
        selector: DeleteFilter,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del session
        must: list[dict[str, object]] = [
            {"key": "tenant_id", "match": {"value": str(selector.tenant_id)}}
        ]
        if selector.collection_id is not None:
            must.append({"key": "collection_id", "match": {"value": str(selector.collection_id)}})
        if selector.document_id is not None:
            must.append({"key": "document_id", "match": {"value": str(selector.document_id)}})
        if selector.index_version is not None:
            must.append({"key": "index_version", "match": {"value": selector.index_version}})
        if selector.chunk_ids:
            must.append(
                {"key": "chunk_id", "match": {"any": [str(item) for item in selector.chunk_ids]}}
            )
        if len(must) == 1 and selector.index_version_ne is None:
            raise ValueError("delete needs a selector")
        before = self._count_filter(store_collection, {"must": must})
        if selector.index_version_ne is not None:
            must.append({"key": "index_version", "match": {"except": [selector.index_version_ne]}})
        self._delete(store_collection, {"must": must}, selector.tenant_id)
        return before

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
        del session
        filt = {
            "must": [
                {"key": "tenant_id", "match": {"value": str(tenant_id)}},
                {"key": "document_id", "match": {"value": str(document_id)}},
            ]
        }
        count = self._count_filter(store_collection, filt)  # type: ignore[arg-type]
        self._invoke(
            "set_payload",
            collection_name=store_collection,
            payload={"acl": list(acl), "classification": classification},
            points=self._filter(filt),  # type: ignore[arg-type]
        )
        return count

    async def search(self, query: HybridQuery) -> list[ScoredChunk]:
        if not query.principals or not query.allowed_classifications:
            raise ValueError("principals and classifications are required")
        filt = build_filter(query)
        name = query.targets[0].store_collection
        dense_hits = self._query(name, filt, dense=list(query.dense), limit=query.dense_k)
        indices, values = _sparse(query.text)
        lexical_hits = self._query(name, filt, sparse=(indices, values), limit=query.lexical_k)
        rows = {
            str(hit.payload["chunk_id"]): (  # type: ignore[attr-defined]
                str(hit.payload["document_id"]),  # type: ignore[attr-defined]
                str(hit.payload["collection_id"]),  # type: ignore[attr-defined]
            )
            for hit in [*dense_hits, *lexical_hits]
        }
        dense = [(str(hit.id), rank) for rank, hit in enumerate(dense_hits, start=1)]  # type: ignore[attr-defined]
        lexical = [(str(hit.id), rank) for rank, hit in enumerate(lexical_hits, start=1)]  # type: ignore[attr-defined]
        return rrf_fuse(dense, lexical, rows, rrf_k=query.rrf_k, fused_k=query.fused_k)

    async def count(
        self, store_collection: str, tenant_id: object, collection_id: object, index_version: int
    ) -> int:
        filt = {
            "must": [
                {"key": "tenant_id", "match": {"value": str(tenant_id)}},
                {"key": "collection_id", "match": {"value": str(collection_id)}},
                {"key": "index_version", "match": {"value": index_version}},
            ]
        }
        return self._count_filter(store_collection, filt)  # type: ignore[arg-type]

    async def export(
        self,
        store_collection: str,
        tenant_id: object,
        collection_id: object,
        index_version: int,
        batch_size: int = 512,
    ) -> AsyncIterator[list[ExportedVector]]:
        filt = {
            "must": [
                {"key": "tenant_id", "match": {"value": str(tenant_id)}},
                {"key": "collection_id", "match": {"value": str(collection_id)}},
                {"key": "index_version", "match": {"value": index_version}},
            ]
        }
        offset = None
        while True:
            scrolled = self._invoke(
                "scroll",
                collection_name=store_collection,
                scroll_filter=self._filter(filt),  # type: ignore[arg-type]
                limit=batch_size,
                offset=offset,
                with_vectors=True,
                with_payload=True,
            )
            page, offset = scrolled if isinstance(scrolled, tuple) else ([], None)
            rows = page if isinstance(page, list) else []
            batch = [
                ExportedVector(
                    chunk_id=uuid.UUID(str(point.payload["chunk_id"])),
                    document_id=uuid.UUID(str(point.payload["document_id"])),
                    index_version=int(point.payload["index_version"]),
                    dense=[float(value) for value in point.vector["dense"]],
                )
                for point in rows
            ]
            batch.sort(key=lambda item: item.chunk_id)
            if batch:
                yield batch
            if offset is None:
                break

    async def health(self) -> StoreHealth:
        url = os.environ.get("AR_QDRANT_URL", "").strip().rstrip("/")
        started = time.perf_counter()
        if not url:
            return StoreHealth(backend="qdrant", ok=False, latency_ms=0, detail="missing url")
        try:
            response = httpx.get(f"{url}/readyz", timeout=2.0)  # noqa: ASYNC210
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StoreUnavailable("qdrant is not ready") from exc
        elapsed = (time.perf_counter() - started) * 1000
        return StoreHealth(backend="qdrant", ok=True, latency_ms=elapsed, detail="ready")

    def _query(
        self,
        name: str,
        filt: dict[str, object],
        *,
        dense: list[float] | None = None,
        sparse: tuple[list[int], list[float]] | None = None,
        limit: int,
    ) -> list[object]:
        models = _models()
        using = "dense"
        vector: object = dense or []
        if sparse is not None:
            using = "lexical"
            vector = models.SparseVector(indices=sparse[0], values=sparse[1])  # type: ignore[attr-defined]
        result = self._invoke(
            "query_points",
            collection_name=name,
            query=vector,
            using=using,
            query_filter=self._filter(filt),
            limit=limit,
            with_payload=True,
        )
        return list(result.points)  # type: ignore[attr-defined]

    def _delete(self, name: str, filt: dict[str, object], tenant_id: object) -> None:
        del tenant_id
        self._invoke("delete", collection_name=name, points_selector=self._filter(filt))

    def _count_filter(self, name: str, filt: dict[str, object]) -> int:
        counted = self._invoke(
            "count", collection_name=name, count_filter=self._filter(filt), exact=True
        )
        return int(counted.count)  # type: ignore[attr-defined]

    def _invoke(self, method: str, **kwargs: object) -> object:
        try:
            fn = getattr(self._client, method)
            return fn(**kwargs)
        except StoreError:
            raise
        except Exception as exc:
            raise StoreUnavailable("qdrant request failed") from exc

    def _filter(self, payload: dict[str, object]) -> object:
        return _models().Filter.model_validate(payload)  # type: ignore[attr-defined]


def _payload(chunk: IndexedChunk) -> dict[str, object]:
    return {
        "chunk_id": str(chunk.chunk_id),
        "tenant_id": str(chunk.tenant_id),
        "collection_id": str(chunk.collection_id),
        "document_id": str(chunk.document_id),
        "source_id": str(chunk.source_id),
        "index_version": chunk.index_version,
        "acl": list(chunk.acl),
        "classification": chunk.classification,
        "title": chunk.title,
    }


def _sparse(text: str) -> tuple[list[int], list[float]]:
    cache = os.environ.get("AR_FASTEMBED_CACHE_DIR", "")
    if cache and Path(cache).is_dir():
        try:
            from fastembed import SparseTextEmbedding  # noqa: PLC0415

            model = SparseTextEmbedding("Qdrant/bm25", cache_dir=cache, local_files_only=True)
            found = next(iter(model.embed([text])))
            return list(found.indices), [float(value) for value in found.values]
        except ImportError, OSError, StopIteration, ValueError:
            return hashed_sparse(text)
    return hashed_sparse(text)

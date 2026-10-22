"""RetrievalStore port. Spec: docs/03-specs/10-knowledge.md §6."""

import uuid
from typing import TYPE_CHECKING, ClassVar, Protocol

from ar_domain.knowledge.store_types import (
    SUPPORTED_DIMS,
    BackendName,
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


class StoreError(Exception):
    """Non-retryable retrieval store failure."""


class StoreUnavailable(StoreError):  # noqa: N818 - name is the retrieval port's
    """Retryable retrieval store failure. Search surfaces ``retrieval_unavailable``."""


class UnsupportedDims(StoreError):  # noqa: N818 - name is the retrieval port's
    """The embedding dimension is not in the backend allowlist."""


def rrf_fuse(
    dense: list[tuple[str, int]],
    lexical: list[tuple[str, int]],
    rows: dict[str, tuple[str, str]],
    *,
    rrf_k: int,
    fused_k: int,
) -> list[ScoredChunk]:
    """Reciprocal rank fusion. Ties break by chunk id ascending."""
    scores: dict[str, float] = {}
    dense_rank: dict[str, int] = {}
    lexical_rank: dict[str, int] = {}
    for chunk_id, rank in dense:
        dense_rank[chunk_id] = rank
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for chunk_id, rank in lexical:
        lexical_rank[chunk_id] = rank
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    fused: list[ScoredChunk] = []
    for chunk_id in ordered[:fused_k]:
        document_id, collection_id = rows[chunk_id]
        fused.append(
            ScoredChunk(
                chunk_id=uuid.UUID(chunk_id),
                document_id=uuid.UUID(document_id),
                collection_id=uuid.UUID(collection_id),
                score=scores[chunk_id],
                dense_rank=dense_rank.get(chunk_id),
                lexical_rank=lexical_rank.get(chunk_id),
            )
        )
    return fused


class RetrievalStore(Protocol):
    """Backend-independent index. Adapters live behind ``get_retrieval_store``."""

    backend: ClassVar[BackendName]
    capabilities: ClassVar[StoreCapabilities]

    async def ensure_collection(self, spec: PhysicalCollectionSpec) -> str: ...

    async def drop_collection(
        self, store_collection: str, tenant_id: object, collection_id: object
    ) -> None: ...

    async def upsert(
        self,
        store_collection: str,
        chunks: Sequence[IndexedChunk],
        *,
        session: AsyncSession | None = None,
    ) -> int: ...

    async def delete(
        self,
        store_collection: str,
        selector: DeleteFilter,
        *,
        session: AsyncSession | None = None,
    ) -> int: ...

    async def set_acl(
        self,
        store_collection: str,
        tenant_id: object,
        document_id: object,
        acl: Sequence[str],
        classification: str,
        *,
        session: AsyncSession | None = None,
    ) -> int: ...

    async def search(self, query: HybridQuery) -> list[ScoredChunk]: ...

    async def count(
        self, store_collection: str, tenant_id: object, collection_id: object, index_version: int
    ) -> int: ...

    def export(
        self,
        store_collection: str,
        tenant_id: object,
        collection_id: object,
        index_version: int,
        batch_size: int = 512,
    ) -> AsyncIterator[list[ExportedVector]]: ...

    async def health(self) -> StoreHealth: ...


def memory_index(holder: object) -> RetrievalStore:
    """Return the process-store index, creating it on first use."""
    from ar_domain.knowledge.store_memory import MemoryRetrievalStore  # noqa: PLC0415

    current = getattr(holder, "retrieval_index", None)
    if isinstance(current, MemoryRetrievalStore):
        return current  # type: ignore[return-value]
    created = MemoryRetrievalStore()
    holder.retrieval_index = created  # type: ignore[attr-defined]
    return created  # type: ignore[return-value]


def get_retrieval_store(backend: str = "pgvector") -> RetrievalStore:
    """Return the adapter named by ``store_backend`` or ``AR_VECTOR_BACKEND``."""
    if backend == "pgvector":
        from ar_domain.knowledge.store_pgvector import PgVectorStore  # noqa: PLC0415

        return PgVectorStore()  # type: ignore[return-value]
    if backend == "qdrant":
        try:
            from ar_domain.knowledge.store_qdrant import QdrantStore  # noqa: PLC0415
        except ImportError as exc:
            raise StoreError("adapter not installed") from exc
        return QdrantStore()  # type: ignore[return-value]
    raise StoreError("adapter not installed")


def supported_dims() -> frozenset[int]:
    return SUPPORTED_DIMS

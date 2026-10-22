"""In-process RetrievalStore used while the dev API stays off Postgres (OQ-31).

The contract matches the pgvector adapter: tenant, ACL and classification
predicates run before the candidate limit, then reciprocal rank fusion.
"""

import math
import time
from typing import TYPE_CHECKING, ClassVar

from ar_domain.knowledge.acl import acl_overlap
from ar_domain.knowledge.store import UnsupportedDims, rrf_fuse
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
    import uuid
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from ar_domain.knowledge.store_types import DeleteFilter


class MemoryRetrievalStore:
    """Process-local index. ``stopped`` makes operations raise ``StoreUnavailable``."""

    backend: ClassVar[str] = "pgvector"
    capabilities: ClassVar[StoreCapabilities] = StoreCapabilities(
        native_sparse=False,
        transactional_with_pg=True,
        supported_dims=SUPPORTED_DIMS,
    )

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, IndexedChunk] = {}
        self.dims: dict[str, int] = {}
        self.stopped = False

    async def ensure_collection(self, spec: PhysicalCollectionSpec) -> str:
        self._live()
        if spec.dims not in SUPPORTED_DIMS:
            raise UnsupportedDims(f"unsupported_embedding_dims:{spec.dims}")
        name = f"pg:{spec.dims}"
        self.dims[name] = spec.dims
        return name

    async def drop_collection(
        self, store_collection: str, tenant_id: object, collection_id: object
    ) -> None:
        del store_collection
        self._live()
        self.rows = {
            key: row
            for key, row in self.rows.items()
            if not (row.tenant_id == tenant_id and row.collection_id == collection_id)
        }

    async def upsert(
        self,
        store_collection: str,
        chunks: Sequence[IndexedChunk],
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del session
        self._live()
        dims = self.dims.get(store_collection)
        written = 0
        for chunk in chunks:
            if dims is not None and len(chunk.dense) != dims:
                raise UnsupportedDims("dense length does not match the collection")
            self.rows[chunk.chunk_id] = chunk
            written += 1
        return written

    async def delete(
        self,
        store_collection: str,
        selector: DeleteFilter,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        del store_collection, session
        self._live()
        doomed = [key for key, row in self.rows.items() if _selected(row, selector)]
        for key in doomed:
            self.rows.pop(key, None)
        return len(doomed)

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
        del store_collection, session
        self._live()
        updated = 0
        for key, row in list(self.rows.items()):
            if row.tenant_id == tenant_id and row.document_id == document_id:
                self.rows[key] = row.model_copy(
                    update={"acl": list(acl), "classification": classification}
                )
                updated += 1
        return updated

    async def search(self, query: HybridQuery) -> list[ScoredChunk]:
        self._live()
        if not query.principals or not query.allowed_classifications:
            raise ValueError("principals and classifications are required")
        matched = [row for row in self.rows.values() if _visible(row, query)]
        dense = _dense_ranks(matched, query.dense, query.dense_k)
        lexical = _lexical_ranks(matched, query.text, query.lexical_k)
        rows = {
            str(row.chunk_id): (str(row.document_id), str(row.collection_id)) for row in matched
        }
        return rrf_fuse(dense, lexical, rows, rrf_k=query.rrf_k, fused_k=query.fused_k)

    async def count(
        self, store_collection: str, tenant_id: object, collection_id: object, index_version: int
    ) -> int:
        del store_collection
        self._live()
        return sum(
            1
            for row in self.rows.values()
            if row.tenant_id == tenant_id
            and row.collection_id == collection_id
            and row.index_version == index_version
        )

    async def export(
        self,
        store_collection: str,
        tenant_id: object,
        collection_id: object,
        index_version: int,
        batch_size: int = 512,
    ) -> AsyncIterator[list[ExportedVector]]:
        del store_collection
        self._live()
        found = [
            row
            for row in self.rows.values()
            if row.tenant_id == tenant_id
            and row.collection_id == collection_id
            and row.index_version == index_version
        ]
        found.sort(key=lambda row: row.chunk_id)
        step = max(1, batch_size)
        for start in range(0, len(found), step):
            batch = found[start : start + step]
            yield [
                ExportedVector(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    index_version=row.index_version,
                    dense=list(row.dense),
                )
                for row in batch
            ]

    async def health(self) -> StoreHealth:
        started = time.perf_counter()
        if self.stopped:
            return StoreHealth(backend="pgvector", ok=False, latency_ms=0, detail="stopped")
        elapsed = (time.perf_counter() - started) * 1000
        return StoreHealth(backend="pgvector", ok=True, latency_ms=elapsed, detail="memory")

    def _live(self) -> None:
        if self.stopped:
            from ar_domain.knowledge.store import StoreUnavailable  # noqa: PLC0415

            raise StoreUnavailable("retrieval store is stopped")


def _visible(row: IndexedChunk, query: HybridQuery) -> bool:
    if row.tenant_id != query.tenant_id:
        return False
    if row.classification not in query.allowed_classifications:
        return False
    if not acl_overlap(list(row.acl), query.principals):
        return False
    return any(
        row.collection_id == target.collection_id and row.index_version == target.index_version
        for target in query.targets
    )


def _selected(row: IndexedChunk, selector: DeleteFilter) -> bool:
    if row.tenant_id != selector.tenant_id:
        return False
    if selector.collection_id is not None and row.collection_id != selector.collection_id:
        return False
    if selector.document_id is not None and row.document_id != selector.document_id:
        return False
    if selector.index_version is not None and row.index_version != selector.index_version:
        return False
    if selector.index_version_ne is not None and row.index_version == selector.index_version_ne:
        return False
    return not selector.chunk_ids or row.chunk_id in selector.chunk_ids


def _dense_ranks(rows: list[IndexedChunk], query: list[float], limit: int) -> list[tuple[str, int]]:
    scored = [(_cosine(query, row.dense), row.chunk_id) for row in rows if row.dense]
    scored.sort(key=lambda item: (-item[0], item[1]))
    ranked = enumerate(scored[:limit], start=1)
    return [(str(chunk_id), rank) for rank, (_score, chunk_id) in ranked]


def _lexical_ranks(rows: list[IndexedChunk], text: str, limit: int) -> list[tuple[str, int]]:
    needle = text.lower()
    tokens = set(needle.split())
    scored: list[tuple[float, uuid.UUID]] = []
    for row in rows:
        haystack = row.lexical_text.lower()
        if needle and needle in haystack:
            score = 1.0
        else:
            overlap = set(haystack.split()) & tokens
            score = len(overlap) / len(tokens) if tokens else 0.0
        if score > 0:
            scored.append((score, row.chunk_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    ranked = enumerate(scored[:limit], start=1)
    return [(str(chunk_id), rank) for rank, (_score, chunk_id) in ranked]


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right)) or 1.0
    )

"""Per-fact hybrid search on Qdrant. Postgres remains the source of the fact.

Dense and sparse (hashed BM25) scores are fused in this process. Each point
stores the embedding model id that produced the dense vector. Proof is
``contract`` against a Qdrant service and ``unit`` with the in-memory double.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from typing import Any  # noqa: TC003

from ar_domain.knowledge.qdrant_filter import hashed_sparse


@dataclass(frozen=True, slots=True)
class MemoryPoint:
    fact_id: uuid.UUID
    tenant_id: uuid.UUID
    scope: str
    text: str
    dense: list[float]
    embedding_model_id: str


class MemoryQdrant:
    """A small hybrid index. ``client`` is a Qdrant client or the test double."""

    def __init__(self, client: Any, collection: str = "memory_facts") -> None:
        self.client = client
        self.collection = collection

    def upsert(self, point: MemoryPoint) -> None:
        indices, values = hashed_sparse(point.text)
        self.client.upsert(
            collection_name=self.collection,
            points=[
                {
                    "id": str(point.fact_id),
                    "dense": list(point.dense),
                    "sparse": {"indices": indices, "values": values},
                    "payload": {
                        "fact_id": str(point.fact_id),
                        "tenant_id": str(point.tenant_id),
                        "scope": point.scope,
                        "embedding_model_id": point.embedding_model_id,
                        "text": point.text,
                    },
                }
            ],
        )

    def search(
        self, *, tenant_id: uuid.UUID, query: str, dense: list[float], limit: int = 8
    ) -> list[dict[str, object]]:
        indices, values = hashed_sparse(query)
        dense_hits = self.client.query(
            self.collection, vector=dense, using="dense", tenant_id=str(tenant_id), limit=limit
        )
        sparse_hits = self.client.query(
            self.collection,
            vector={"indices": indices, "values": values},
            using="sparse",
            tenant_id=str(tenant_id),
            limit=limit,
        )
        fused = _fuse([_ids(dense_hits), _ids(sparse_hits)])
        by_id = {str(hit.get("id")): hit for hit in [*dense_hits, *sparse_hits]}
        rows: list[dict[str, object]] = []
        for fact_id, score in fused[:limit]:
            hit = by_id.get(fact_id, {})
            payload = hit.get("payload") if isinstance(hit.get("payload"), dict) else {}
            rows.append(
                {
                    "fact_id": fact_id,
                    "score": score,
                    "embedding_model_id": str(payload.get("embedding_model_id") or ""),
                    "text": str(payload.get("text") or ""),
                    "scope": str(payload.get("scope") or ""),
                }
            )
        return rows


class MemoryQdrantDouble:
    """In-process stand-in so unit tests do not open a socket."""

    def __init__(self) -> None:
        self.points: dict[str, dict[str, object]] = {}

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]) -> None:
        del collection_name
        for point in points:
            self.points[str(point["id"])] = point

    def query(
        self,
        collection: str,
        *,
        vector: object,
        using: str,
        tenant_id: str,
        limit: int,
    ) -> list[dict[str, object]]:
        del collection, vector, using, limit
        found: list[dict[str, object]] = []
        for point in self.points.values():
            payload = point.get("payload")
            if isinstance(payload, dict) and str(payload.get("tenant_id")) == tenant_id:
                found.append(point)
        return found


def _ids(hits: list[dict[str, object]]) -> list[str]:
    return [str(hit.get("id")) for hit in hits]


def _fuse(lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal rank fusion over two hit lists."""
    scores: dict[str, float] = {}
    for hits in lists:
        for rank, item in enumerate(hits, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))

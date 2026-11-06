"""Backend-independent retrieval. Spec: docs/03-specs/10-knowledge.md §6.4."""

import os
import time
from typing import TYPE_CHECKING

from ar_domain.knowledge.store import rrf_fuse
from ar_domain.knowledge.store_types import HybridQuery, ScoredChunk, SearchTarget

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ar_domain.knowledge.store import RetrievalStore
    from ar_domain.models.embedding import ModelTarget


async def search_targets(
    store: RetrievalStore,
    *,
    tenant_id: object,
    text: str,
    dense: list[float],
    targets: Sequence[SearchTarget],
    principals: list[str],
    allowed: list[str],
    top_k: int,
) -> tuple[list[ScoredChunk], dict[str, float]]:
    """Search one backend. Returns fused hits and stage timings in milliseconds."""
    started = time.perf_counter()
    query = HybridQuery(
        tenant_id=tenant_id,
        text=text,
        dense=dense,
        targets=list(targets),
        principals=principals,
        allowed_classifications=allowed,
        fused_k=max(top_k, 50),
    )
    fused = await store.search(query)
    store_ms = (time.perf_counter() - started) * 1000
    return fused, {"store_ms": store_ms}


def merge_groups(
    groups: list[list[ScoredChunk]], *, rrf_k: int = 60, fused_k: int = 50
) -> list[ScoredChunk]:
    """Fuse hits that came from different backends or embedding sizes."""
    dense: list[tuple[str, int]] = []
    rows: dict[str, tuple[str, str]] = {}
    for group in groups:
        for rank, hit in enumerate(sorted(group, key=lambda item: -item.score), start=1):
            dense.append((str(hit.chunk_id), rank))
            rows[str(hit.chunk_id)] = (str(hit.document_id), str(hit.collection_id))
    return rrf_fuse(dense, [], rows, rrf_k=rrf_k, fused_k=fused_k)


def apply_rerank(
    query: str,
    hits: list[dict[str, object]],
    *,
    top_k: int,
    min_score: float | None = None,
    target: ModelTarget | None = None,
) -> tuple[list[dict[str, object]], float, str | None, bool]:
    """Score the top candidates against the question with the tenant's rerank model.

    Returns the hits to keep, the time taken, a warning, and whether the hits were scored.
    A rerank model gives each passage a score from 0 to 1, and passages under the bar
    are dropped: ``min_score`` when the caller sets one, else the model's own
    (``rerank_floor``), because each model scores on its own scale. Without a model, or
    when it fails, nothing here can say how well a passage answers the question: the
    closest passages are returned in the order the search found them, and the model that
    reads them judges them.
    """
    limit = int(os.environ.get("AR_KNOWLEDGE_RERANK_CANDIDATES", "50"))
    window = hits[:limit]
    if target is None:
        return window[:top_k], 0.0, None, False
    from ar_domain.models.embedding import rerank, rerank_floor  # noqa: PLC0415

    bar = rerank_floor(target) if min_score is None else min_score
    started = time.perf_counter()
    documents = [str(hit.get("rerank_text") or hit.get("snippet") or "") for hit in window]
    try:
        scores = rerank(target, query, documents)
    except Exception:  # noqa: BLE001 - rerank is optional; the search order still answers
        return window[:top_k], (time.perf_counter() - started) * 1000, "rerank_unavailable", False
    elapsed = (time.perf_counter() - started) * 1000
    ranked: list[dict[str, object]] = []
    for hit, score in zip(window, scores, strict=False):
        copied = dict(hit)
        copied["rerank_score"] = score
        ranked.append(copied)
    ranked.sort(key=lambda item: (-float(item["rerank_score"]), str(item.get("chunk_id"))))  # type: ignore[arg-type]
    kept = [hit for hit in ranked if float(hit["rerank_score"]) >= bar][:top_k]  # type: ignore[arg-type]
    return kept, elapsed, None, True


def _number(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def answerable(hits: list[dict[str, object]]) -> bool:
    """True when a rerank model kept at least one passage: ``apply_rerank`` drops the rest."""
    return any(hit.get("rerank_score") is not None for hit in hits)

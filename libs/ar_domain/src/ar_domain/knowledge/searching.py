"""Playground and tool search. Spec: docs/03-specs/10-knowledge.md §6.4."""

import time
from typing import TYPE_CHECKING, Any

from ar_domain.knowledge.access import (
    can_read_document,
    can_see,
    clearance,
    principals,
    readable_classes,
)
from ar_domain.knowledge.embedder import embed_texts
from ar_domain.knowledge.fetchers import check_access
from ar_domain.knowledge.metrics import SEARCH_HITS, SEARCH_SECONDS, UNANSWERABLE
from ar_domain.knowledge.retrieval import answerable, apply_rerank
from ar_domain.knowledge.store import StoreUnavailable, memory_index
from ar_domain.knowledge.store_types import HybridQuery, SearchTarget
from ar_domain.knowledge.syncutil import run_sync

if TYPE_CHECKING:
    import uuid


def search(
    store: Any,
    actor: Any,
    *,
    query: str,
    collection_ids: list[uuid.UUID],
    top_k: int,
    debug: bool,
    min_score: float = 0.2,
) -> dict[str, object]:
    """Hybrid search filtered by the caller's principals. Managers are not exempt."""
    started = time.perf_counter()
    targets, collections = _targets(store, actor, collection_ids)
    if not targets:
        return {"hits": [], "answerable": False}
    dense = embed_texts([query], model=_model(collections), dimensions=_dims(collections))[0]
    hybrid = HybridQuery(
        tenant_id=actor.tenant_id,
        text=query,
        dense=dense,
        targets=targets,
        principals=principals(store, actor),
        allowed_classifications=readable_classes(store, actor),
        fused_k=max(top_k, 20),
    )
    index = memory_index(store)
    try:
        with SEARCH_SECONDS.labels(stage="store").time():
            fused = run_sync(index.search(hybrid))
    except StoreUnavailable as exc:
        raise StoreUnavailable("retrieval_unavailable") from exc
    hits = [_hit(store, row) for row in fused]
    reranked, rerank_ms, warning = apply_rerank(query, hits, top_k=top_k, min_score=min_score)
    verified = _late(store, actor, reranked, collections)
    ok = answerable(verified, min_score=min_score)
    if not ok:
        UNANSWERABLE.inc()
    SEARCH_HITS.observe(len(verified))
    body: dict[str, object] = {"hits": verified, "answerable": ok}
    if warning:
        body["warning"] = warning
    if debug:
        body["debug"] = {
            "backend": "memory",
            "dense": [str(row.chunk_id) for row in fused if row.dense_rank],
            "lexical": [str(row.chunk_id) for row in fused if row.lexical_rank],
            "fused": [str(row.chunk_id) for row in fused],
            "store_ms": 0,
            "rerank_ms": rerank_ms,
            "total_ms": (time.perf_counter() - started) * 1000,
            "clearance": clearance(store, actor),
        }
    return body


def _targets(
    store: Any, actor: Any, collection_ids: list[uuid.UUID]
) -> tuple[list[SearchTarget], list[dict[str, object]]]:
    targets: list[SearchTarget] = []
    collections: list[dict[str, object]] = []
    for collection_id in collection_ids:
        row = store.knowledge_collections.get(collection_id)
        if not isinstance(row, dict) or not can_see(actor, row):
            continue
        collections.append(row)
        targets.append(
            SearchTarget(
                collection_id=row["id"],
                index_version=int(row.get("index_version") or 1),
                store_collection=str(row.get("store_collection") or "pg:1024"),
                text_search_config=str(row.get("text_search_config") or "simple"),
            )
        )
    return targets, collections


def _hit(store: Any, row: Any) -> dict[str, object]:
    chunk = store.document_chunks.get(row.chunk_id, {})
    document = store.knowledge_documents.get(row.document_id, {})
    heading = chunk.get("heading_path") if isinstance(chunk, dict) else []
    text = str(chunk.get("text") if isinstance(chunk, dict) else "")
    title = str(document.get("title") if isinstance(document, dict) else "")
    prefix = str(chunk.get("context_prefix") if isinstance(chunk, dict) else "")
    path = " / ".join(str(item) for item in heading) if isinstance(heading, list) else ""
    return {
        "document_id": row.document_id,
        "chunk_id": row.chunk_id,
        "collection_id": row.collection_id,
        "title": title,
        "uri": str(document.get("uri") if isinstance(document, dict) else ""),
        "snippet": text[:500],
        "score": row.score,
        "rerank_score": row.score,
        "page_from": chunk.get("page_from") if isinstance(chunk, dict) else None,
        "page_to": chunk.get("page_to") if isinstance(chunk, dict) else None,
        "heading_path": heading if isinstance(heading, list) else [],
        "rerank_text": "\n".join(part for part in (title, path, prefix, text) if part),
        "external_id": str(document.get("external_id") if isinstance(document, dict) else ""),
        "source_id": document.get("source_id") if isinstance(document, dict) else None,
    }


def _late(
    store: Any,
    actor: Any,
    hits: list[dict[str, object]],
    collections: list[dict[str, object]],
) -> list[dict[str, object]]:
    by_id = {row.get("id"): row for row in collections}
    kept: list[dict[str, object]] = []
    for hit in hits:
        collection = by_id.get(hit.get("collection_id"))
        document = store.knowledge_documents.get(hit.get("document_id"))
        if not isinstance(collection, dict) or not isinstance(document, dict):
            continue
        if not can_read_document(store, actor, document, collection):
            continue
        if collection.get("sensitivity") == "high":
            source = store.knowledge_sources.get(document.get("source_id"))
            if isinstance(source, dict):
                try:
                    allowed = check_access(
                        source, str(document.get("external_id") or ""), str(actor.user_id)
                    )
                except OSError, TimeoutError, ValueError:
                    allowed = False
                if not allowed:
                    from ar_domain.knowledge.metrics import LATE_DENIED  # noqa: PLC0415

                    LATE_DENIED.inc()
                    continue
        kept.append(hit)
    return kept


def _model(collections: list[dict[str, object]]) -> str:
    if not collections:
        return "fake-embed"
    return str(collections[0].get("embedding_model") or "fake-embed")


def _dims(collections: list[dict[str, object]]) -> int:
    if not collections:
        return 1024
    return int(collections[0].get("dims") or 1024)  # type: ignore[call-overload,no-any-return]

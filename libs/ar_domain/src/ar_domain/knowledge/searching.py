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
from ar_domain.knowledge.embedding import collection_dims, embed_for_collection
from ar_domain.knowledge.fetchers import check_access
from ar_domain.knowledge.metrics import SEARCH_HITS, SEARCH_SECONDS, UNANSWERABLE
from ar_domain.knowledge.retrieval import answerable, apply_rerank
from ar_domain.knowledge.store import StoreUnavailable, active_index
from ar_domain.knowledge.store_types import HybridQuery, SearchTarget
from ar_domain.knowledge.syncutil import run_sync
from ar_domain.models.embedding import refresh_registry, rerank_model

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
    min_score: float | None = None,
) -> dict[str, object]:
    """Sync wrapper for callers that are not already on the request loop."""
    return run_sync(
        search_async(
            store,
            actor,
            query=query,
            collection_ids=collection_ids,
            top_k=top_k,
            debug=debug,
            min_score=min_score,
        )
    )


async def search_async(
    store: Any,
    actor: Any,
    *,
    query: str,
    collection_ids: list[uuid.UUID],
    top_k: int,
    debug: bool,
    min_score: float | None = None,
) -> dict[str, object]:
    """Hybrid search filtered by the caller's principals. Managers are not exempt."""
    await refresh_registry(store)
    started = time.perf_counter()
    targets, collections = _targets(store, actor, collection_ids)
    if not targets:
        return {"hits": [], "answerable": False}
    index = active_index(store)
    fused: list[Any] = []
    # A question is embedded once for each model that indexed a searched collection.
    for group in _by_model(targets, collections):
        hybrid = HybridQuery(
            tenant_id=actor.tenant_id,
            text=query,
            dense=embed_for_collection(store, group[0][1], [query])[0],
            targets=[target for target, _row in group],
            principals=principals(store, actor),
            allowed_classifications=readable_classes(store, actor),
            fused_k=max(top_k, 20),
        )
        try:
            with SEARCH_SECONDS.labels(stage="store").time():
                fused.extend(await index.search(hybrid))
        except StoreUnavailable as exc:
            raise StoreUnavailable("retrieval_unavailable") from exc
    hits = [_hit(store, row) for row in fused]
    reranker = rerank_model(store, actor.tenant_id)
    reranked, rerank_ms, warning, scored = apply_rerank(
        query, hits, top_k=top_k, min_score=min_score, target=reranker
    )
    verified = _late(store, actor, reranked, collections)
    # Scored passages answer the question when one clears the bar. Unscored ones are the
    # closest the search found, and whoever reads them decides.
    ok = answerable(verified) if scored else bool(verified)
    if not ok:
        UNANSWERABLE.inc()
    SEARCH_HITS.observe(len(verified))
    body: dict[str, object] = {
        "hits": verified,
        "answerable": ok,
        "embedding_model": str(collections[0].get("embedding_model") or ""),
        "rerank_model": reranker.name if reranker is not None else "",
        "scored": scored,
    }
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


def _by_model(
    targets: list[SearchTarget], collections: list[dict[str, object]]
) -> list[list[tuple[SearchTarget, dict[str, object]]]]:
    """Searched collections grouped by the model and vector length that indexed them."""
    groups: dict[tuple[str, str, int | None], list[tuple[SearchTarget, dict[str, object]]]] = {}
    for target, row in zip(targets, collections, strict=True):
        key = (
            str(row.get("embedding_model_id") or ""),
            str(row.get("embedding_model") or ""),
            collection_dims(row),
        )
        groups.setdefault(key, []).append((target, row))
    return list(groups.values())


def _hit(store: Any, row: Any) -> dict[str, object]:
    chunk = store.document_chunks.get(row.chunk_id, {})
    document = store.knowledge_documents.get(row.document_id, {})
    heading = chunk.get("heading_path") if isinstance(chunk, dict) else []
    text = str(chunk.get("text") if isinstance(chunk, dict) else "")
    title = str(document.get("title") if isinstance(document, dict) else "")
    prefix = str(chunk.get("context_prefix") if isinstance(chunk, dict) else "")
    path = " / ".join(str(item) for item in heading) if isinstance(heading, list) else ""
    anchor = prefix[7:] if prefix.startswith("anchor:") else ""
    external = str(document.get("external_id") if isinstance(document, dict) else "")
    library_id = external.split(":", 1)[1] if external.startswith("library:") else ""
    return {
        "document_id": row.document_id,
        "chunk_id": row.chunk_id,
        "collection_id": row.collection_id,
        "title": title,
        "uri": str(document.get("uri") if isinstance(document, dict) else ""),
        "snippet": text[:500],
        "text": text[:2000],
        "anchor": anchor,
        "page": chunk.get("page_from") if isinstance(chunk, dict) else None,
        "heading": path,
        "library_document_id": library_id,
        "score": row.score,
        "similarity": getattr(row, "similarity", None),
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

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
from ar_domain.knowledge.embedding import (
    collection_dims,
    embed_for_collection,
    refuse_embedding_mismatch,
)
from ar_domain.knowledge.fetchers import current_acl, map_item_acl
from ar_domain.knowledge.metrics import SEARCH_HITS, SEARCH_SECONDS, UNANSWERABLE
from ar_domain.knowledge.retrieval import (
    answerable,
    apply_rerank,
    diversify,
    max_per_document,
)
from ar_domain.knowledge.retrieval import (
    candidate_k as candidate_pool,
)
from ar_domain.knowledge.store import StoreUnavailable, active_index
from ar_domain.knowledge.store_types import HybridQuery, SearchTarget
from ar_domain.knowledge.syncutil import run_sync
from ar_domain.knowledge.threshold import clears, retrieval_bar
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
    document_ids: list[uuid.UUID] | None = None,
    candidate_k: int | None = None,
    max_passages_per_document: int | None = None,
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
            document_ids=document_ids,
            candidate_k=candidate_k,
            max_passages_per_document=max_passages_per_document,
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
    document_ids: list[uuid.UUID] | None = None,
    candidate_k: int | None = None,
    max_passages_per_document: int | None = None,
) -> dict[str, object]:
    """Hybrid search filtered by the caller's principals. Managers are not exempt."""
    clock = _Stages()
    await refresh_registry(store)
    from ar_domain.durable.hydrate import refresh_knowledge  # noqa: PLC0415

    # What another process indexed since this one last looked is found by this search.
    await refresh_knowledge(store, actor.tenant_id)
    clock.lap("refresh")
    started = time.perf_counter()
    targets, collections = _targets(store, actor, collection_ids)
    if not targets:
        return {"hits": [], "answerable": False}
    refuse_embedding_mismatch(store, collections)
    index = active_index(store)
    fused: list[Any] = []
    named = tuple(document_ids or ())
    bar = min_score if min_score is not None else retrieval_bar(store, actor.tenant_id, {})
    pool = max(top_k, candidate_pool(candidate_k))
    share = max_per_document(max_passages_per_document)
    # A question is embedded once for each model that indexed a searched collection.
    for group in _by_model(targets, collections):
        clock.lap("prepare")
        dense = embed_for_collection(store, group[0][1], [query])[0]
        clock.lap("embed")
        hybrid = HybridQuery(
            tenant_id=actor.tenant_id,
            text=query,
            dense=dense,
            targets=[target for target, _row in group],
            principals=principals(store, actor),
            allowed_classifications=readable_classes(store, actor),
            dense_k=pool,
            lexical_k=pool,
            fused_k=pool,
            document_ids=named,
        )
        try:
            fused.extend(await index.search(hybrid))
        except StoreUnavailable as exc:
            raise StoreUnavailable("retrieval_unavailable") from exc
        clock.lap("store")
    hits = [_hit(store, row) for row in fused]
    reranker = rerank_model(store, actor.tenant_id)
    reranked, rerank_ms, warning, scored = apply_rerank(
        query, hits, top_k=pool, min_score=bar, target=reranker, window=pool
    )
    clock.lap("rerank")
    if bar is not None and not scored:
        reranked = [hit for hit in reranked if clears(hit, bar)]
    verified = diversify(
        _late(store, actor, reranked, collections), top_k=top_k, per_document=share
    )
    clock.lap("verify")
    timings = clock.done()
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
        # How long each stage took, so a slow search says which stage was slow.
        "timings_ms": timings,
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


class _Stages:
    """Times the stages of one search. Each stage is also a ``ar_knowledge_search_seconds``
    sample, and the whole set is logged once, with no query or passage text."""

    def __init__(self) -> None:
        self._began = self._last = time.perf_counter()
        self._ms: dict[str, float] = {}

    def lap(self, stage: str) -> None:
        now = time.perf_counter()
        spent = now - self._last
        self._last = now
        self._ms[stage] = round(self._ms.get(stage, 0.0) + spent * 1000, 1)
        SEARCH_SECONDS.labels(stage=stage).observe(spent)

    def done(self) -> dict[str, float]:
        timings = {**self._ms, "total": round((time.perf_counter() - self._began) * 1000, 1)}
        from ar_common.logging import get_logger  # noqa: PLC0415

        get_logger(__name__).info("knowledge_search_timed", **timings)
        return timings


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
                allowed = _still_allowed(store, actor, source, document, collection)
                if not allowed:
                    from ar_domain.knowledge.metrics import LATE_DENIED  # noqa: PLC0415

                    LATE_DENIED.inc()
                    continue
        kept.append(hit)
    return kept


def _still_allowed(
    store: Any,
    actor: Any,
    source: dict[str, object],
    document: dict[str, object],
    collection: dict[str, object],
) -> bool:
    """Ask the source who may read the document now. No answer is a refusal.

    A kind whose documents take the collection's readers has nothing more to ask: the
    check made on the indexed readers stands.
    """
    import httpx  # noqa: PLC0415

    from ar_common.errors import ArError  # noqa: PLC0415

    try:
        readers = current_acl({**source, "store": store}, str(document.get("external_id") or ""))
    except OSError, TimeoutError, ValueError, httpx.HTTPError, ArError:
        return False
    if readers is None:
        return True
    principals, _unmapped = map_item_acl({"acl": readers}, store)
    return can_read_document(store, actor, {**document, "acl_principals": principals}, collection)

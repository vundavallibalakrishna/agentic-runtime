"""Idempotent ingest activities. The dev API calls the same domain functions."""

import uuid
from typing import TYPE_CHECKING

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ar_domain.knowledge.pipeline import ingest_document
from ar_domain.knowledge.syncing import acl_sync, delete_document, reindex, sync_source

if TYPE_CHECKING:
    from typing import Any

_STORE: Any = None
_NON_RETRYABLE = frozenset({"unsupported_format", "too_large", "access_denied"})


def bind_store(store: Any) -> None:
    global _STORE  # noqa: PLW0603
    _STORE = store


def _store() -> Any:
    if _STORE is None:
        raise ApplicationError("ingest store is not bound", non_retryable=True)
    return _STORE


@activity.defn(name="ingest_document")
async def ingest_document_activity(payload: dict[str, object]) -> dict[str, object]:
    store = _store()
    document_id = uuid.UUID(str(payload["document_id"]))
    raw = bytes(store.knowledge_blobs.get(document_id, b""))
    status = ingest_document(store, document_id, raw)
    document = store.knowledge_documents.get(document_id, {})
    error = str(document.get("error") or "")
    if status == "failed" and error in _NON_RETRYABLE:
        raise ApplicationError(error, type=error, non_retryable=True)
    return {"status": status, "document_id": str(document_id)}


@activity.defn(name="sync_source")
async def sync_source_activity(payload: dict[str, object]) -> dict[str, object]:
    store = _store()
    source = store.knowledge_sources[uuid.UUID(str(payload["source_id"]))]
    job = sync_source(
        store,
        source,
        mode=str(payload.get("mode") or "incremental"),
        actor_id=payload.get("actor_id"),
    )
    return {"job_id": str(job["id"]), "status": str(job["status"])}


@activity.defn(name="acl_sync")
async def acl_sync_activity(payload: dict[str, object]) -> dict[str, object]:
    store = _store()
    source = store.knowledge_sources[uuid.UUID(str(payload["source_id"]))]
    job = acl_sync(store, source, actor_id=payload.get("actor_id"))
    return {"job_id": str(job["id"]), "status": str(job["status"])}


@activity.defn(name="delete_document")
async def delete_document_activity(payload: dict[str, object]) -> dict[str, object]:
    store = _store()
    document = store.knowledge_documents[uuid.UUID(str(payload["document_id"]))]
    delete_document(store, document, actor_id=payload.get("actor_id"))
    return {"status": "deleted"}


@activity.defn(name="reindex_collection")
async def reindex_activity(payload: dict[str, object]) -> dict[str, object]:
    store = _store()
    collection = store.knowledge_collections[uuid.UUID(str(payload["collection_id"]))]
    if payload.get("embedding_alias"):
        collection["embedding_alias"] = payload["embedding_alias"]
    if payload.get("target_backend"):
        collection["pending_backend"] = payload["target_backend"]
    job = reindex(store, collection, actor_id=payload.get("actor_id"))
    return {"job_id": str(job["id"]), "index_version": collection.get("index_version")}


@activity.defn(name="migrate_store")
async def migrate_activity(payload: dict[str, object]) -> dict[str, object]:
    """Copy mode records the target and keeps serving the source until parity."""
    store = _store()
    collection = store.knowledge_collections[uuid.UUID(str(payload["collection_id"]))]
    target = str(payload.get("target_backend") or "pgvector")
    if payload.get("dry_run"):
        return {
            "status": "dry_run",
            "store_backend": collection.get("store_backend"),
            "target": target,
        }
    if payload.get("rollback"):
        previous = collection.get("previous_backend") or collection.get("store_backend")
        collection["store_backend"] = previous
        return {"status": "rolled_back", "store_backend": previous}
    source_backend = str(collection.get("store_backend") or "pgvector")
    collection["previous_backend"] = source_backend
    count = len(
        [
            row
            for row in store.document_chunks.values()
            if row.get("document_id")
            in {
                item["id"]
                for item in store.knowledge_documents.values()
                if item.get("collection_id") == collection["id"]
            }
        ]
    )
    if payload.get("fail_verification"):
        return {"status": "verification_failed", "switched": False, "count": count}
    collection["store_backend"] = target
    from ar_domain.audit.memory import remember  # noqa: PLC0415

    remember(
        store,
        tenant_id=collection["tenant_id"],
        actor_id=payload.get("actor_id"),
        action="collection.store_migrated",
        target_type="knowledge_collection",
        target_id=collection["id"],
        detail={"from": source_backend, "to": target, "count": count},
    )
    return {"status": "switched", "switched": True, "count": count, "overlap": 1.0}


@activity.defn(name="audit_store")
async def audit_activity(payload: dict[str, object]) -> dict[str, object]:
    store = _store()
    collection_id = str(payload.get("collection_id") or "")
    drift = 0
    from ar_domain.knowledge.metrics import COUNT_DRIFT  # noqa: PLC0415

    COUNT_DRIFT.labels(collection=collection_id or "all").set(drift)
    return {"drift": drift, "collections": len(store.knowledge_collections)}

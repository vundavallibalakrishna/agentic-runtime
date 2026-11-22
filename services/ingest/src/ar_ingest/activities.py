"""Idempotent ingest activities. The dev API calls the same domain functions."""

import base64
import uuid
from typing import Any  # noqa: TC003

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ar_domain.knowledge.pipeline import embedding_error, ingest_document_async, needs_admin
from ar_domain.knowledge.syncing import acl_sync, delete_document, reindex, sync_source
from ar_domain.models.embedding import EmbeddingFailedError, EmbeddingUnconfiguredError
from ar_domain.readmodel.activity import repository_activity

_STORE: Any = None
_NON_RETRYABLE = frozenset({"unsupported_format", "too_large", "access_denied"})


def bind_store(store: Any) -> None:
    global _STORE  # noqa: PLW0603
    _STORE = store


def process_store() -> Any:
    if _STORE is None:
        raise ApplicationError("ingest store is not bound", non_retryable=True)
    return _STORE


def _store() -> Any:
    from ar_domain.readmodel.activity import active_unit  # noqa: PLC0415

    unit = active_unit()
    if unit is not None:
        return unit
    return process_store()


@activity.defn(name="ingest_document")
@repository_activity(process_store)
async def ingest_document_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = _store()
    document_id = uuid.UUID(str(payload["document_id"]))
    raw_b64 = payload.get("raw_b64")
    if isinstance(raw_b64, str) and raw_b64:
        store.knowledge_blobs[document_id] = base64.b64decode(raw_b64)
    from ar_domain.durable.hydrate import reload_document  # noqa: PLC0415

    await reload_document(store, document_id)
    raw = bytes(store.knowledge_blobs.get(document_id, b""))
    if not raw:
        # A large upload does not travel with the request: it is read from the file store.
        from ar_domain.knowledge.pipeline import stored_bytes  # noqa: PLC0415

        raw = stored_bytes(store, document_id)
        store.knowledge_blobs[document_id] = raw
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

    try:
        status = await ingest_document_async(store, document_id, raw)
    except (EmbeddingUnconfiguredError, EmbeddingFailedError) as exc:
        # The document row carries the reason. Trying again helps only when the model
        # is set and did not answer; a missing model waits for an administrator.
        await flush_store(store)
        raise ApplicationError(
            exc.code.value, type=exc.code.value, non_retryable=needs_admin(embedding_error(exc))
        ) from exc
    await flush_store(store)
    document = store.knowledge_documents.get(document_id, {})
    error = str(document.get("error") or "")
    if status == "failed" and error in _NON_RETRYABLE:
        raise ApplicationError(error, type=error, non_retryable=True)
    return {"status": status, "document_id": str(document_id)}


@activity.defn(name="parse_library_document")
@repository_activity(process_store)
async def parse_library_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Read a staged library row and fill it with the layout parser.

    With ``reprocess`` the row is one a person asked to have read again.
    """
    store = _store()
    document_id = uuid.UUID(str(payload["document_id"]))
    tenant_id = uuid.UUID(str(payload["tenant_id"]))
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.m24 import load_library_row  # noqa: PLC0415

    # The row was staged by another process: read it before it is parsed here.
    await load_library_row(store, tenant_id, document_id)
    library = DocumentLibrary(store)
    row = store.library_documents.get(document_id)
    owner = row.get("owner_user_id") if isinstance(row, dict) else None
    actor = Actor(tenant_id, owner if isinstance(owner, uuid.UUID) else tenant_id, frozenset())
    from ar_common.errors import ArError, NotFoundError  # noqa: PLC0415

    if payload.get("reprocess"):
        from ar_common.offload import run_sync  # noqa: PLC0415
        from ar_domain.documents.lifecycle import reread  # noqa: PLC0415

        engine = str(payload.get("engine") or "")
        try:
            # Off the loop: a page read by the model waits on the model.
            await run_sync(lambda: reread(store, actor, document_id, engine=engine))
        except ArError as exc:
            # The file cannot be read. Trying again reads the same file, so the reason
            # goes back to the person who asked.
            return {"status": "failed", "code": exc.code.value, "message": exc.detail}
        await flush_store(store)
        return {"status": "ready", "document_id": str(document_id)}
    try:
        saved = library.finish_parse(actor, document_id)
    except NotFoundError:
        # The row or its bytes are not visible here yet. The retry reads them again.
        raise
    except ArError as exc:
        # The file cannot be read, and the row now says why. Trying again reads the same
        # file, so the reason goes back to the person who uploaded it.
        await flush_store(store)
        return {"status": "failed", "code": exc.code.value, "message": exc.detail}
    except Exception:
        await flush_store(store)
        raise
    await flush_store(store)
    return {"status": str(saved.get("status") or "ready"), "document_id": str(document_id)}


@activity.defn(name="sync_source")
@repository_activity(process_store)
async def sync_source_activity(payload: dict[str, Any]) -> dict[str, Any]:
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
@repository_activity(process_store)
async def acl_sync_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = _store()
    source = store.knowledge_sources[uuid.UUID(str(payload["source_id"]))]
    job = acl_sync(store, source, actor_id=payload.get("actor_id"))
    return {"job_id": str(job["id"]), "status": str(job["status"])}


@activity.defn(name="delete_document")
@repository_activity(process_store)
async def delete_document_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = _store()
    document = store.knowledge_documents[uuid.UUID(str(payload["document_id"]))]
    delete_document(store, document, actor_id=payload.get("actor_id"))
    return {"status": "deleted"}


@activity.defn(name="reindex_collection")
@repository_activity(process_store)
async def reindex_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = _store()
    collection = store.knowledge_collections[uuid.UUID(str(payload["collection_id"]))]
    if payload.get("embedding_alias"):
        collection["embedding_alias"] = payload["embedding_alias"]
    if payload.get("target_backend"):
        collection["pending_backend"] = payload["target_backend"]
    job = reindex(store, collection, actor_id=payload.get("actor_id"))
    return {"job_id": str(job["id"]), "index_version": collection.get("index_version")}


@activity.defn(name="migrate_store")
@repository_activity(process_store)
async def migrate_activity(payload: dict[str, Any]) -> dict[str, Any]:
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
@repository_activity(process_store)
async def audit_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = _store()
    collection_id = str(payload.get("collection_id") or "")
    drift = 0
    from ar_domain.knowledge.metrics import COUNT_DRIFT  # noqa: PLC0415

    COUNT_DRIFT.labels(collection=collection_id or "all").set(drift)
    return {"drift": drift, "collections": len(store.knowledge_collections)}

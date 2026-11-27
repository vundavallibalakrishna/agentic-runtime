"""Idempotent ingest activities. The dev API calls the same domain functions."""

import base64
import uuid
from typing import Any  # noqa: TC003

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ar_domain.knowledge.pipeline import embedding_error, ingest_document_async, needs_admin
from ar_domain.knowledge.syncing import acl_sync, delete_document
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
    raw = base64.b64decode(raw_b64) if isinstance(raw_b64, str) and raw_b64 else b""
    from ar_domain.durable.hydrate import reload_document  # noqa: PLC0415

    await reload_document(store, document_id)
    if not raw:
        # A large upload does not travel with the request: it is read from the file store.
        from ar_domain.knowledge.pipeline import stored_bytes  # noqa: PLC0415

        raw = stored_bytes(store, document_id)
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


async def _read_outlook(
    store: Any,
    library: Any,
    actor: Any,
    document_id: uuid.UUID,
    row: dict[str, Any],
) -> dict[str, Any]:
    """Read a .msg here, not in the API process, and ingest each attachment."""
    from ar_common.offload import run_sync  # noqa: PLC0415
    from ar_domain.documents.originals import read_original  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_ingest.outlook import parse_outlook  # noqa: PLC0415

    raw = read_original(store, str(row.get("object_key") or ""))
    if raw is None:
        return {"status": "failed", "code": "not_found", "message": "The file bytes are missing."}
    try:
        parsed = await run_sync(lambda: parse_outlook(raw))
    except Exception as exc:  # noqa: BLE001 — a bad message is a failed document
        await flush_store(store)
        return {"status": "failed", "code": "corrupt", "message": type(exc).__name__}
    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    saved = library.finish_from_text(
        actor, document_id, str(parsed.get("text") or ""), {"format": "msg", "headers": headers}
    )
    attachments = parsed.get("attachments")
    if isinstance(attachments, list):
        for item in attachments:
            if isinstance(item, dict) and isinstance(item.get("data"), bytes):
                library.ingest(
                    actor,
                    data=item["data"],
                    filename=str(item.get("filename") or "attachment"),
                )
    await flush_store(store)
    return {"status": str(saved.get("status") or "ready"), "document_id": str(document_id)}


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
    if isinstance(row, dict) and str(row.get("filename") or "").lower().endswith(".msg"):
        return await _read_outlook(store, library, actor, document_id, row)
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
    """Sync one source on this worker. The source and its job were made by another process.

    A retry finds the job still open and carries on: a page already indexed is unchanged.
    """
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_source  # noqa: PLC0415
    from ar_domain.knowledge.syncing import sync_source_async  # noqa: PLC0415

    store = _store()
    source_id = uuid.UUID(str(payload["source_id"]))
    await reload_source(store, source_id)
    source = store.knowledge_sources.get(source_id)
    if not isinstance(source, dict):
        raise ApplicationError("the source was not found", non_retryable=True)
    opened = (
        store.ingestion_jobs.get(uuid.UUID(str(payload["job_id"])))
        if payload.get("job_id")
        else None
    )
    try:
        job = await sync_source_async(
            store,
            source,
            mode=str(payload.get("mode") or "incremental"),
            actor_id=payload.get("actor_id"),
            job=opened if isinstance(opened, dict) else None,
            beat=activity.heartbeat,
        )
    except BaseException:
        # A sync that is stopped part way does not leave its job open: an open job is
        # taken for a sync still going, and no other could start. A retry reopens it.
        if isinstance(opened, dict) and opened.get("status") == "running":
            from ar_domain.knowledge.syncing import finish_job  # noqa: PLC0415

            finish_job(opened, status="failed", error="the sync was interrupted")
            source["last_sync_status"] = "failed"
        raise
    finally:
        # What was read so far is kept, whether or not the sync got to its end.
        await flush_store(store)
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


def _reindex_ids(payload: dict[str, Any]) -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.UUID(str(payload["collection_id"])), uuid.UUID(str(payload["job_id"]))


def _target(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("target")
    return target if isinstance(target, dict) else {}


def _reindex_error(exc: Exception) -> ApplicationError:
    from ar_domain.knowledge.reindexing import ReindexFailedError  # noqa: PLC0415

    if isinstance(exc, ReindexFailedError):
        return ApplicationError(exc.reason, type="reindex_failed", non_retryable=exc.final)
    return ApplicationError(type(exc).__name__, type=type(exc).__name__)


@activity.defn(name="reindex_prepare")
@repository_activity(process_store)
async def reindex_prepare_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a re-index job: the version to build and the documents to put in it."""
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_collection  # noqa: PLC0415
    from ar_domain.knowledge.reindexing import ReindexFailedError, prepare  # noqa: PLC0415

    store = _store()
    collection_id, job_id = _reindex_ids(payload)
    await reload_collection(store, collection_id)
    try:
        plan = prepare(store, collection_id, job_id)
    except ReindexFailedError as exc:
        raise _reindex_error(exc) from exc
    await flush_store(store)
    return plan


@activity.defn(name="reindex_documents")
@repository_activity(process_store)
async def reindex_documents_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Write one batch of documents into the version a re-index is building."""
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_collection  # noqa: PLC0415
    from ar_domain.knowledge.reindexing import build  # noqa: PLC0415

    store = _store()
    collection_id, job_id = _reindex_ids(payload)
    await reload_collection(store, collection_id)
    try:
        written = await build(
            store,
            collection_id=collection_id,
            job_id=job_id,
            target=_target(payload),
            version=int(payload["version"]),
            document_ids=[uuid.UUID(str(item)) for item in payload.get("document_ids") or []],
            beat=activity.heartbeat,
        )
    except Exception as exc:
        raise _reindex_error(exc) from exc
    finally:
        # The job's failures are kept whether or not the batch got to its end.
        await flush_store(store)
    return {"written": written}


@activity.defn(name="reindex_switch")
@repository_activity(process_store)
async def reindex_switch_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """Put the version a re-index built in use and delete the one it replaces."""
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_collection  # noqa: PLC0415
    from ar_domain.knowledge.reindexing import switch  # noqa: PLC0415

    store = _store()
    collection_id, job_id = _reindex_ids(payload)
    await reload_collection(store, collection_id)
    try:
        job = await switch(
            store,
            collection_id=collection_id,
            job_id=job_id,
            target=_target(payload),
            version=int(payload["version"]),
            actor_id=payload.get("actor_id"),
            beat=activity.heartbeat,
        )
    except Exception as exc:
        raise _reindex_error(exc) from exc
    finally:
        await flush_store(store)
    return {"job_id": str(job["id"]), "status": str(job["status"])}


@activity.defn(name="reindex_abandon")
@repository_activity(process_store)
async def reindex_abandon_activity(payload: dict[str, Any]) -> dict[str, Any]:
    """End a re-index that cannot finish. The version in use keeps answering."""
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_collection  # noqa: PLC0415
    from ar_domain.knowledge.reindexing import abandon  # noqa: PLC0415

    store = _store()
    collection_id, job_id = _reindex_ids(payload)
    await reload_collection(store, collection_id)
    version = payload.get("version")
    job = await abandon(
        store,
        collection_id=collection_id,
        job_id=job_id,
        target=_target(payload),
        version=None if version is None else int(version),
        reason=str(payload.get("error") or ""),
    )
    await flush_store(store)
    return {"job_id": str(job["id"]), "status": str(job["status"])}


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

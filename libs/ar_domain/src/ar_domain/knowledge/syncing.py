"""Source sync, ACL sync, reindex and delete. Activities call the same functions."""

import hashlib
from typing import TYPE_CHECKING, Any

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.knowledge.access import as_uuid
from ar_domain.knowledge.fetchers import fetch_bytes, list_acl_changes, list_changes, map_item_acl
from ar_domain.knowledge.pipeline import ingest_document
from ar_domain.knowledge.store import memory_index
from ar_domain.knowledge.store_types import DeleteFilter
from ar_domain.knowledge.syncutil import run_sync

if TYPE_CHECKING:
    import uuid


def open_job(
    store: Any,
    *,
    tenant_id: uuid.UUID,
    collection_id: uuid.UUID,
    source_id: uuid.UUID | None,
    kind: str,
    triggered_by: str,
) -> dict[str, object]:
    job_id = new_id()
    now = utcnow()
    row = {  # type: ignore[var-annotated]
        "id": job_id,
        "tenant_id": tenant_id,
        "source_id": source_id,
        "collection_id": collection_id,
        "kind": kind,
        "status": "running",
        "temporal_workflow_id": f"{kind}-{job_id}",
        "stats": {"seen": 0, "added": 0, "updated": 0, "unchanged": 0, "deleted": 0, "failed": 0},
        "error": None,
        "failures": [],
        "triggered_by": triggered_by,
        "started_at": now,
        "finished_at": None,
        "created_at": now,
    }
    store.ingestion_jobs[job_id] = row
    return row  # type: ignore[return-value]


def finish_job(job: dict[str, object], *, status: str, error: str | None = None) -> None:
    job["status"] = status
    job["error"] = error
    job["finished_at"] = utcnow()


def sync_source(
    store: Any, source: dict[str, object], *, mode: str, actor_id: object
) -> dict[str, object]:
    """Ingest changed items and delete tombstones. Unchanged bytes are a no-op."""
    running = _running(store, source["id"], "full_sync" if mode == "full" else "incremental_sync")
    if running is not None:
        return running
    kind = "full_sync" if mode == "full" else "incremental_sync"
    job = open_job(
        store,
        tenant_id=as_uuid(source["tenant_id"]),
        collection_id=as_uuid(source["collection_id"]),
        source_id=as_uuid(source["id"]),
        kind=kind,
        triggered_by="manual",
    )
    page = list_changes(source, mode=mode)
    seen: set[str] = set()
    items = page.get("items") if isinstance(page.get("items"), list) else []
    for item in items:  # type: ignore[attr-defined]
        if not isinstance(item, dict):
            continue
        external_id = str(item.get("external_id") or "")
        seen.add(external_id)
        _stats(job)["seen"] = int(_stats(job)["seen"]) + 1  # type: ignore[call-overload]
        try:
            _upsert_item(store, source, item, mode=mode, job=job, actor_id=actor_id)
        except (OSError, ValueError) as exc:
            _fail(job, external_id, str(exc))
    deleted = page.get("deleted_external_ids")
    if isinstance(deleted, list):
        for external_id in deleted:
            _delete_external(store, source, str(external_id), actor_id=actor_id)
            _stats(job)["deleted"] = int(_stats(job)["deleted"]) + 1  # type: ignore[call-overload]
    if mode == "full":
        for document in _source_documents(store, source["id"]):
            if str(document.get("external_id")) not in seen and document.get("status") != "deleted":
                delete_document(store, document, actor_id=actor_id)
                _stats(job)["deleted"] = int(_stats(job)["deleted"]) + 1  # type: ignore[call-overload]
    source["cursor"] = page.get("next_cursor") if isinstance(page.get("next_cursor"), dict) else {}
    source["last_sync_at"] = utcnow()
    failed = int(_stats(job)["failed"])  # type: ignore[call-overload]
    status = "partially_failed" if failed else "succeeded"
    source["last_sync_status"] = status
    finish_job(job, status=status)
    return job


def acl_sync(store: Any, source: dict[str, object], *, actor_id: object) -> dict[str, object]:
    """Update principals and the index without embedding again."""
    job = open_job(
        store,
        tenant_id=as_uuid(source["tenant_id"]),
        collection_id=as_uuid(source["collection_id"]),
        source_id=as_uuid(source["id"]),
        kind="acl_sync",
        triggered_by="manual",
    )
    index = memory_index(store)
    collection = store.knowledge_collections[source["collection_id"]]
    for change in list_acl_changes(source):
        external_id = str(change.get("external_id") or "")
        document = _by_external(store, source["id"], external_id)
        if document is None:
            continue
        principals, unmapped = map_item_acl({"acl": change.get("acl")}, store)
        digest = hashlib.sha256("|".join(sorted(principals)).encode()).hexdigest()
        if digest == document.get("acl_hash"):
            _stats(job)["unchanged"] = int(_stats(job)["unchanged"]) + 1  # type: ignore[call-overload]
            continue
        document["acl_principals"] = principals
        document["acl_hash"] = digest
        stats = _stats(job)
        stats["unmapped_principals"] = int(stats.get("unmapped_principals") or 0) + unmapped  # type: ignore[call-overload]
        run_sync(
            index.set_acl(
                str(collection.get("store_collection")),
                document["tenant_id"],
                document["id"],
                principals,
                str(document.get("classification") or "internal"),
            )
        )
        stats["updated"] = int(stats["updated"]) + 1  # type: ignore[call-overload]
        remember(
            store,
            tenant_id=source["tenant_id"],
            actor_id=actor_id,
            action="document.classified",
            target_type="document",
            target_id=document["id"],
            detail={"acl": principals},
        )
    finish_job(job, status="succeeded")
    return job


def reindex(store: Any, collection: dict[str, object], *, actor_id: object) -> dict[str, object]:
    """Blue/green: keep serving the old version until every document is reindexed."""
    job = open_job(
        store,
        tenant_id=as_uuid(collection["tenant_id"]),
        collection_id=as_uuid(collection["id"]),
        source_id=None,
        kind="reindex",
        triggered_by="manual",
    )
    previous = int(collection.get("index_version") or 1)  # type: ignore[call-overload]
    collection["index_version"] = previous
    pending = previous + 1
    for document in _collection_documents(store, collection["id"]):
        if document.get("status") == "deleted":
            continue
        raw = bytes(getattr(store, "knowledge_blobs", {}).get(document["id"], b""))
        document["status"] = "pending"
        document["version_hash"] = ""
        collection["index_version"] = pending
        ingest_document(store, as_uuid(document["id"]), raw)
        collection["index_version"] = previous
        _stats(job)["updated"] = int(_stats(job)["updated"]) + 1  # type: ignore[call-overload]
    collection["index_version"] = pending
    index = memory_index(store)
    for document in _collection_documents(store, collection["id"]):
        run_sync(
            index.delete(
                str(collection.get("store_collection")),
                DeleteFilter(
                    tenant_id=as_uuid(document["tenant_id"]),
                    document_id=as_uuid(document["id"]),
                    index_version=previous,
                ),
            )
        )
    finish_job(job, status="succeeded")
    remember(
        store,
        tenant_id=collection["tenant_id"],
        actor_id=actor_id,
        action="collection.reindexed",
        target_type="knowledge_collection",
        target_id=collection["id"],
        detail={"index_version": pending},
    )
    return job


def delete_document(store: Any, document: dict[str, object], *, actor_id: object) -> None:
    collection = store.knowledge_collections.get(document.get("collection_id"))
    index = memory_index(store)
    if isinstance(collection, dict):
        run_sync(
            index.delete(
                str(collection.get("store_collection")),
                DeleteFilter(
                    tenant_id=as_uuid(document["tenant_id"]),
                    document_id=as_uuid(document["id"]),
                ),
            )
        )
    stale = [
        key
        for key, row in store.document_chunks.items()
        if row.get("document_id") == document.get("id")
    ]
    for key in stale:
        store.document_chunks.pop(key, None)
    blobs = getattr(store, "knowledge_blobs", None)
    if isinstance(blobs, dict):
        blobs.pop(document.get("id"), None)
    document["status"] = "deleted"
    document["updated_at"] = utcnow()
    store.domain_events.append(
        {
            "type": "document.deleted",
            "tenant_id": str(document["tenant_id"]),
            "document_id": str(document["id"]),
        }
    )
    remember(
        store,
        tenant_id=document["tenant_id"],
        actor_id=actor_id,
        action="document.deleted",
        target_type="document",
        target_id=document["id"],
        detail={"title": str(document.get("title") or "")},
    )


def _upsert_item(
    store: Any,
    source: dict[str, object],
    item: dict[str, object],
    *,
    mode: str,
    job: dict[str, object],
    actor_id: object,
) -> None:
    external_id = str(item.get("external_id") or "")
    raw, mime = fetch_bytes(item)
    digest = hashlib.sha256(raw).hexdigest()
    existing = _by_external(store, source["id"], external_id)
    hint = str(item.get("version_hint") or digest)
    if (
        existing is not None
        and mode != "full"
        and existing.get("status") == "indexed"
        and (existing.get("version_hash") == digest or existing.get("version_hint") == hint)
    ):
        _stats(job)["unchanged"] = int(_stats(job)["unchanged"]) + 1  # type: ignore[call-overload]
        return
    principals, unmapped = map_item_acl(item, store)
    if not principals:
        principals = _collection_default(store, source)
    created = existing is None
    document = existing or _stub(store, source, item, mime, principals)
    document["mime_type"] = mime
    document["title"] = str(item.get("title") or document.get("title") or external_id)
    document["acl_principals"] = principals
    document["acl_hash"] = hashlib.sha256("|".join(sorted(principals)).encode()).hexdigest()
    document["version_hint"] = hint
    blobs = store.knowledge_blobs
    blobs[document["id"]] = raw
    if unmapped:
        current = int(_stats(job).get("unmapped_principals") or 0)  # type: ignore[call-overload]
        _stats(job)["unmapped_principals"] = current + unmapped
    status = ingest_document(store, as_uuid(document["id"]), raw)
    if status == "failed":
        _fail(job, external_id, str(document.get("error") or "failed"))
        return
    key = "added" if created else "updated"
    if status == "unchanged":
        key = "unchanged"
    _stats(job)[key] = int(_stats(job)[key]) + 1  # type: ignore[call-overload]
    del actor_id


def _stub(
    store: Any,
    source: dict[str, object],
    item: dict[str, object],
    mime: str,
    principals: list[str],
) -> dict[str, object]:
    document_id = new_id()
    now = utcnow()
    row = {
        "id": document_id,
        "tenant_id": source["tenant_id"],
        "collection_id": source["collection_id"],
        "source_id": source["id"],
        "external_id": str(item.get("external_id") or document_id),
        "uri": str(item.get("uri") or item.get("external_id") or ""),
        "title": str(item.get("title") or "Untitled"),
        "mime_type": mime,
        "version_hash": "",
        "size_bytes": 0,
        "language": None,
        "classification": str(item.get("classification") or "internal"),
        "acl_principals": principals,
        "acl_hash": "",
        "summary": "",
        "status": "pending",
        "error": None,
        "indexed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    store.knowledge_documents[document_id] = row
    return row


def _collection_default(store: Any, source: dict[str, object]) -> list[str]:
    collection = store.knowledge_collections.get(source.get("collection_id"))
    if not isinstance(collection, dict):
        return []
    if collection.get("acl_mode") != "collection":
        return []
    from ar_domain.knowledge.acl import collection_acl  # noqa: PLC0415

    return collection_acl(
        visibility=str(collection.get("visibility") or "tenant"),
        owner_team_id=None
        if collection.get("owner_team_id") is None
        else str(collection["owner_team_id"]),
        created_by=None if collection.get("created_by") is None else str(collection["created_by"]),
    )


def _delete_external(
    store: Any, source: dict[str, object], external_id: str, *, actor_id: object
) -> None:
    document = _by_external(store, source["id"], external_id)
    if document is not None and document.get("status") != "deleted":
        delete_document(store, document, actor_id=actor_id)


def _by_external(store: Any, source_id: object, external_id: str) -> dict[str, object] | None:
    for row in store.knowledge_documents.values():
        if row.get("source_id") == source_id and str(row.get("external_id")) == external_id:
            return row  # type: ignore[no-any-return]
    return None


def _source_documents(store: Any, source_id: object) -> list[dict[str, object]]:
    return [row for row in store.knowledge_documents.values() if row.get("source_id") == source_id]


def _collection_documents(store: Any, collection_id: object) -> list[dict[str, object]]:
    return [
        row
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection_id
    ]


def _running(store: Any, source_id: object, kind: str) -> dict[str, object] | None:
    for row in store.ingestion_jobs.values():
        same_source = row.get("source_id") == source_id and row.get("kind") == kind
        if same_source and row.get("status") == "running":
            return row  # type: ignore[no-any-return]
    return None


def _stats(job: dict[str, object]) -> dict[str, object]:
    stats = job.get("stats")
    if not isinstance(stats, dict):
        stats = {}
        job["stats"] = stats
    return stats


def _fail(job: dict[str, object], external_id: str, error: str) -> None:
    _stats(job)["failed"] = int(_stats(job)["failed"]) + 1  # type: ignore[call-overload]
    failures = job.get("failures")
    if not isinstance(failures, list):
        failures = []
        job["failures"] = failures
    if len(failures) < 100:
        failures.append({"external_id": external_id, "error": error})

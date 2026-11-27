"""Re-index a collection blue/green, in steps the ingest worker runs.

Spec: docs/03-specs/10-knowledge.md §4.5. A re-index reads every document again from its
stored bytes and writes its passages into the next ``index_version`` with the settings
asked for. The collection row keeps describing the version in use, which keeps
answering searches, until every document is in the new one. Then one write switches the
collection to the new version and settings, and the old version's passages and vectors
are deleted from the store that holds them. A re-index that cannot finish leaves the old
version in use, removes what it had written and says why on its job.

The API opens the job and starts ``ReindexCollectionWorkflow`` (``knowledge.dispatch``);
each function here is one idempotent activity of that workflow.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.knowledge.access import as_uuid
from ar_domain.knowledge.parse import ParseError
from ar_domain.knowledge.pipeline import _stats as collection_stats
from ar_domain.knowledge.pipeline import embedding_error, index_into_version, stored_bytes
from ar_domain.knowledge.store_types import DeleteFilter
from ar_domain.knowledge.syncing import _fail, _index_of, _stats, finish_job

if TYPE_CHECKING:
    from collections.abc import Callable


# The collection fields a re-index changes, written together at the switch.
TARGET_FIELDS = (
    "embedding_alias",
    "embedding_model",
    "embedding_model_id",
    "store_collection",
    "text_search_config",
    "chunking",
)

# The jobs of a re-index that has not ended.
OPEN = frozenset({"queued", "running"})


class ReindexFailedError(Exception):
    """A re-index cannot finish. ``reason`` is what its job says; ``final`` means trying
    the same step again cannot help until someone changes something."""

    def __init__(self, reason: str, *, final: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.final = final


def open_reindex(store: Any, collection_id: object) -> dict[str, object] | None:
    """The re-index of this collection that has not ended, if there is one."""
    for row in store.ingestion_jobs.values():
        same = row.get("collection_id") == collection_id and row.get("kind") == "reindex"
        if same and row.get("status") in OPEN:
            return row  # type: ignore[no-any-return]
    return None


def building(collection: dict[str, object], target: dict[str, object]) -> dict[str, object]:
    """The collection as it will be once the new version is in use."""
    view = dict(collection)
    for key in TARGET_FIELDS:
        if key in target:
            view[key] = target[key]
    if view.get("embedding_model_id") is not None:
        view["embedding_model_id"] = as_uuid(view["embedding_model_id"])
    return view


def prepare(store: Any, collection_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, object]:
    """Start the job and name the version to build and the documents to put in it.

    The documents are the ones the version in use holds. One that failed or is still
    waiting is not in that version, and is indexed by its own ingest.
    """
    collection = _collection(store, collection_id)
    job = _job(store, job_id)
    job["status"] = "running"
    job["error"] = None
    job["started_at"] = job.get("started_at") or utcnow()
    documents = [str(row["id"]) for row in _documents(store, collection_id)]
    _stats(job)["seen"] = len(documents)
    return {
        "version": _version(collection) + 1,
        "document_ids": documents,
    }


async def build(
    store: Any,
    *,
    collection_id: uuid.UUID,
    job_id: uuid.UUID,
    target: dict[str, object],
    version: int,
    document_ids: list[uuid.UUID],
    beat: Callable[[], object] | None = None,
) -> int:
    """Write these documents into ``version``. Returns how many were written.

    Writing a document again replaces only what it has in ``version``, so a batch that is
    tried again does the same work again and ends in the same place. A document whose
    bytes cannot be read fails the re-index: switching without it would drop it from
    every search.
    """
    collection = _collection(store, collection_id)
    job = _job(store, job_id)
    view = building(collection, target)
    written = 0
    failed: list[object] = []
    for document_id in document_ids:
        document = store.knowledge_documents.get(document_id)
        if not isinstance(document, dict) or document.get("status") == "deleted":
            continue
        reason = await _write(store, document, view, version)
        if reason:
            _fail(job, str(document.get("external_id") or document_id), reason)
            failed.append(document_id)
        else:
            written += 1
        if callable(beat):
            beat()
    if failed:
        # The job's stats are saved with it: they name the documents, up to 20.
        named = _stats(job).get("unreadable")
        known = [str(item) for item in named] if isinstance(named, list) else []
        _stats(job)["unreadable"] = (
            known + [str(item) for item in failed if str(item) not in known]
        )[:20]
        raise ReindexFailedError(_unreadable(len(failed)), final=True)
    return written


async def switch(
    store: Any,
    *,
    collection_id: uuid.UUID,
    job_id: uuid.UUID,
    target: dict[str, object],
    version: int,
    actor_id: object,
    beat: Callable[[], object] | None = None,
) -> dict[str, object]:
    """Put the new version in use, then delete the old one's passages and vectors.

    A document indexed by its own ingest while the re-index ran replaced its passages in
    the version in use, and has none in the new one. It is written now, before the switch.
    """
    collection = _collection(store, collection_id)
    job = _job(store, job_id)
    held = _held(store, version)
    missing = [
        uuid.UUID(str(row["id"]))
        for row in _documents(store, collection_id)
        if row["id"] not in held
    ]
    if missing:
        await build(
            store,
            collection_id=collection_id,
            job_id=job_id,
            target=target,
            version=version,
            document_ids=missing,
            beat=beat,
        )
    stats = _stats(job)
    if _version(collection) != version:
        # What the switch replaces is kept on the job, so a switch tried again after the
        # collection was saved still knows which version to delete.
        stats["previousVersion"] = _version(collection)
        stats["previousStore"] = str(collection.get("store_collection") or "")
        for key, value in building(collection, target).items():
            if key in TARGET_FIELDS:
                collection[key] = value
        collection["index_version"] = version
        collection["updated_at"] = now = utcnow()
        # Every document is in a new version. Saying so is how a process that holds an
        # older copy of the collection knows to read its passages again.
        for row in _documents(store, collection_id):
            row["indexed_at"] = now
        collection_stats(store, collection)
        await _save(store)
    previous = int(str(stats.get("previousVersion") or version - 1))
    await _drop_version(store, collection, str(stats.get("previousStore") or ""), previous)
    current = {row["id"] for row in _documents(store, collection_id)}
    stats["updated"] = len(_held(store, version) & current)
    finish_job(job, status="succeeded")
    remember(
        store,
        tenant_id=collection["tenant_id"],
        actor_id=actor_id,
        action="collection.reindexed",
        target_type="knowledge_collection",
        target_id=collection["id"],
        detail={"index_version": version, "previous_version": previous},
    )
    return job


async def abandon(
    store: Any,
    *,
    collection_id: uuid.UUID,
    job_id: uuid.UUID,
    target: dict[str, object],
    version: int | None,
    reason: str,
) -> dict[str, object]:
    """End a re-index that cannot finish. The version in use is left as it is."""
    job = _job(store, job_id)
    collection = store.knowledge_collections.get(collection_id)
    in_use = _version(collection) if isinstance(collection, dict) else None
    if isinstance(collection, dict) and version is not None and version != in_use:
        view = building(collection, target)
        await _drop_version(store, collection, str(view.get("store_collection") or ""), version)
    finish_job(job, status="failed", error=reason or "the re-index stopped")
    return job


async def _write(
    store: Any, document: dict[str, object], view: dict[str, object], version: int
) -> str:
    """Write one document into ``version``. Returns why it could not be, or nothing."""
    from ar_domain.models.embedding import (  # noqa: PLC0415
        EmbeddingFailedError,
        EmbeddingUnconfiguredError,
    )

    document_id = as_uuid(document["id"])
    raw = stored_bytes(store, document_id)
    if not raw:
        return "the document's file is not stored, so it cannot be read again"
    try:
        await index_into_version(store, document_id, raw, building=view, version=version)
    except ParseError as exc:
        return exc.code
    except (EmbeddingUnconfiguredError, EmbeddingFailedError) as exc:
        from ar_domain.knowledge.pipeline import needs_admin  # noqa: PLC0415

        reason = embedding_error(exc)
        raise ReindexFailedError(reason, final=needs_admin(reason)) from exc
    return ""


async def _drop_version(
    store: Any, collection: dict[str, object], store_collection: str, version: int
) -> None:
    """Delete one version of a collection's passages and vectors."""
    if store_collection:
        index = _index_of(store, {**collection, "store_collection": store_collection})
        await index.delete(
            store_collection,
            DeleteFilter(
                tenant_id=as_uuid(collection["tenant_id"]),
                collection_id=as_uuid(collection["id"]),
                index_version=version,
            ),
        )
    documents = {
        row["id"]
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection["id"]
    }
    stale = [
        key
        for key, row in store.document_chunks.items()
        if row.get("document_id") in documents and int(row.get("index_version") or 1) == version
    ]
    for key in stale:
        store.document_chunks.pop(key, None)
    await _delete_stored_version(store, collection["id"], version)


async def _delete_stored_version(store: Any, collection_id: object, version: int) -> None:
    if not getattr(store, "durable", False):
        return
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415

    from ar_domain.db.engine import engine_here  # noqa: PLC0415

    async with engine_here(store) as engine:
        if engine is None:
            return
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            from ar_domain.durable.flush import _set_tenant_context  # noqa: PLC0415

            await _set_tenant_context(session, store)
            # The vectors of a pgvector collection go with their passages.
            await session.execute(
                text(
                    "DELETE FROM document_chunks c USING documents d "
                    "WHERE d.id = c.document_id AND d.collection_id = :collection "
                    "AND c.index_version = :version"
                ),
                {"collection": collection_id, "version": version},
            )


async def _save(store: Any) -> None:
    if getattr(store, "durable", False):
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        await flush_store(store)


def _held(store: Any, version: int) -> set[object]:
    """The documents that have passages in ``version``."""
    return {
        row.get("document_id")
        for row in store.document_chunks.values()
        if int(row.get("index_version") or 1) == version
    }


def _documents(store: Any, collection_id: object) -> list[dict[str, object]]:
    return [
        row
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection_id and row.get("status") == "indexed"
    ]


def _collection(store: Any, collection_id: uuid.UUID) -> dict[str, object]:
    collection = store.knowledge_collections.get(collection_id)
    if not isinstance(collection, dict):
        raise ReindexFailedError("the collection was deleted", final=True)
    return collection


def _job(store: Any, job_id: uuid.UUID) -> dict[str, object]:
    job = store.ingestion_jobs.get(job_id)
    if not isinstance(job, dict):
        raise ReindexFailedError("the job of this re-index was not found", final=True)
    return job


def _version(collection: dict[str, object]) -> int:
    return int(str(collection.get("index_version") or 1))


def _unreadable(count: int) -> str:
    # The job's stats name the documents. The reason travels through the workflow engine,
    # so it names none.
    return (
        f"{count} document(s) could not be read again (the job's stats name them). The "
        "collection still answers from its current index. Remove or re-add those "
        "documents, then re-index again."
    )

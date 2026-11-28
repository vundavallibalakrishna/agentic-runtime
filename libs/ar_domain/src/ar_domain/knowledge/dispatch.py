"""Where a knowledge source's sync runs.

A sync reads a whole source: for a website that is hundreds of pages, each parsed and
embedded. On an install with workers that is the ingest worker's job, which has the
parsers and does not hold up the API. The caller opens the sync's job, hands it over and
returns. An install with no workflow engine has one process, and the sync runs in it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.knowledge.syncing import (
    _running,
    finish_job,
    open_sync,
    sync_kind,
    sync_source_async,
)

if TYPE_CHECKING:
    from typing import Any


async def request_sync(
    store: Any, source: dict[str, object], *, mode: str, actor_id: object
) -> dict[str, object]:
    """Start one sync of a source and return its job. A sync already going is returned."""
    client = getattr(store, "temporal_client", None)
    if (
        client is None
        or getattr(store, "_ingest_worker", False)
        or not hasattr(client, "start_workflow")
    ):
        return await sync_source_async(store, source, mode=mode, actor_id=actor_id)
    running = _running(store, source["id"], sync_kind(mode))
    if running is not None:
        return running
    job = open_sync(store, source, mode)
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

    # The worker reads the source and the job from the database.
    await flush_store(store)
    try:
        await client.start_workflow(
            "SourceSyncWorkflow",
            {
                "tenant_id": str(source["tenant_id"]),
                "source_id": str(source["id"]),
                "job_id": str(job["id"]),
                "mode": mode,
                "actor_id": None if actor_id is None else str(actor_id),
            },
            id=f"ks-sync-{source['id']}-{job['id']}",
            task_queue="ar-ingest",
        )
    except Exception as exc:  # noqa: BLE001 - the job says why the sync did not start
        finish_job(
            job, status="failed", error=f"the sync could not be started ({type(exc).__name__})"
        )
        source["last_sync_status"] = "failed"
    return job


async def request_reindex(
    store: Any, collection: dict[str, object], target: dict[str, object], *, actor_id: object
) -> dict[str, object]:
    """Queue a re-index of a collection on the ingest worker and return its job.

    A re-index reads and embeds every document again, which takes minutes for a large
    collection, so it is never done inside a request: the job is opened, the workflow is
    started and the caller returns. ``target`` holds the collection settings the new
    version is built with; the collection takes them when the new version is in use. With
    no workflow engine connected nothing can run it, and the caller is told so.
    """
    from ar_common.errors import ArError, ConflictError, ErrorCode  # noqa: PLC0415
    from ar_domain.knowledge.access import as_uuid  # noqa: PLC0415
    from ar_domain.knowledge.reindexing import open_reindex  # noqa: PLC0415
    from ar_domain.knowledge.syncing import open_job  # noqa: PLC0415

    client = getattr(store, "temporal_client", None)
    if client is None or not hasattr(client, "start_workflow"):
        raise ArError(
            ErrorCode.UNAVAILABLE,
            "Re-indexing runs on the ingest worker, and no workflow engine is connected. "
            "Start the workflow engine (Temporal) and the ingest worker, then try again.",
        )
    if open_reindex(store, collection["id"]) is not None:
        raise ConflictError("a re-index of this collection is already running")
    workflow_id = f"reindex-{collection['id']}"
    job = open_job(
        store,
        tenant_id=as_uuid(collection["tenant_id"]),
        collection_id=as_uuid(collection["id"]),
        source_id=None,
        kind="reindex",
        triggered_by="manual",
        status="queued",
        workflow_id=workflow_id,
    )
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

    # The worker reads the collection and the job from the database.
    await flush_store(store)
    try:
        await client.start_workflow(
            "ReindexCollectionWorkflow",
            {
                "tenant_id": str(collection["tenant_id"]),
                "collection_id": str(collection["id"]),
                "job_id": str(job["id"]),
                "target": target,
                "actor_id": None if actor_id is None else str(actor_id),
            },
            # One re-index of a collection at a time, whichever API replica is asked.
            id=workflow_id,
            task_queue="ar-ingest",
        )
    except Exception as exc:  # noqa: BLE001 - the job says why the re-index did not start
        running = type(exc).__name__ == "WorkflowAlreadyStartedError"
        finish_job(
            job,
            status="failed",
            error="another re-index of this collection is running"
            if running
            else f"the re-index could not be started ({type(exc).__name__})",
        )
    return job

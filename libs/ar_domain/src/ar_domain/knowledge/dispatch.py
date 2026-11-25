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

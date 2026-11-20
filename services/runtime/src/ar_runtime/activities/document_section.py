"""One section of a document task. A retry reads the stored result."""

from __future__ import annotations

import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_domain.readmodel.activity import repository_activity
from ar_runtime.activities.expire_approval import current_store, process_store
from ar_runtime.activities.heartbeat import heartbeating


@activity.defn(name="document_section")
@repository_activity(process_store)
async def document_section(payload: dict[str, Any]) -> dict[str, Any]:
    """Read one section of the run's documents and store the result."""
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    section = payload.get("section")
    if store is None or not isinstance(section, dict):
        return {"status": "missing", "run_id": str(run_id)}
    from ar_domain.documents.sections import run_section  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    await reload_run(store, run_id)
    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict):
        return {"status": "missing", "run_id": str(run_id)}
    async with heartbeating():
        result = run_section(store, run, section)
    await flush_store(store)
    return {"status": "ok", "run_id": str(run_id), "anchor": result.get("anchor")}

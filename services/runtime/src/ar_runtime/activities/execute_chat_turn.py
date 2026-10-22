"""Run one chat turn. The activity is safe to retry once the run has finished."""

import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_runtime.activities.expire_approval import current_store


@activity.defn(name="execute_chat_turn")
async def execute_chat_turn(payload: dict[str, Any]) -> dict[str, str]:
    """Reload the queued run, generate the answer, and flush it."""
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None or not hasattr(store, "generate"):
        return {"status": "missing_store", "run_id": str(run_id)}
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415

    await reload_run(store, run_id)
    text = str(payload.get("text") or "")
    raw_names = payload.get("names")
    names = [str(item) for item in raw_names] if isinstance(raw_names, list) else []
    await store.generate(run_id, text, names)
    await flush_store(store)
    runs = getattr(store, "runs", None)
    run = runs.get(run_id, {}) if isinstance(runs, dict) else {}
    status = str(run.get("status") or "completed") if isinstance(run, dict) else "completed"
    return {"status": status, "run_id": str(run_id)}

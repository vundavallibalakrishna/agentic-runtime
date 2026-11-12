"""One research phase or one sub-task. The activity is safe to run again."""

import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_domain.readmodel.activity import repository_activity
from ar_runtime.activities.expire_approval import current_store, process_store
from ar_runtime.activities.heartbeat import heartbeating


def _run(store: object, run_id: uuid.UUID) -> dict[str, object] | None:
    runs = getattr(store, "runs", None)
    if not isinstance(runs, dict):
        return None
    found = runs.get(run_id)
    return found if isinstance(found, dict) else None


@activity.defn(name="research_step")
@repository_activity(process_store)
async def research_step(payload: dict[str, Any]) -> dict[str, object]:
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None:
        return {"status": "missing_store", "kind": "final", "run_id": str(run_id)}
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415
    from ar_domain.research.driver import advance_research, store_results  # noqa: PLC0415
    from ar_domain.research.engine import pending_subtasks, state_of  # noqa: PLC0415
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(store)
    await reload_run(store, run_id)
    run = _run(store, run_id)
    if run is None:
        return {"status": "missing", "kind": "final", "run_id": str(run_id)}
    if str(run.get("status") or "") == "cancelled":
        return {"status": "cancelled", "kind": "final", "run_id": str(run_id)}
    text = str(payload.get("text") or "")
    store_results(run, payload.get("results"))
    async with heartbeating():
        kind = await advance_research(store, run, text, one_step=True)
    await flush_store(store)
    state = state_of(run, text)
    return {
        "status": str(run.get("status") or "running"),
        "kind": kind,
        "run_id": str(run_id),
        "subtasks": pending_subtasks(state) if kind == "fanout" else [],
    }


@activity.defn(name="research_subtask")
@repository_activity(process_store)
async def research_subtask(payload: dict[str, Any]) -> dict[str, object]:
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None:
        return {"status": "missing_store"}
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415
    from ar_domain.research.driver import execute_subtask  # noqa: PLC0415
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(store)
    await reload_run(store, run_id)
    run = _run(store, run_id)
    if run is None or str(run.get("status") or "") == "cancelled":
        return {"status": "cancelled"}
    query = {"id": str(payload.get("id") or ""), "text": str(payload.get("text") or "")}
    async with heartbeating():
        result = await execute_subtask(store, run, query)
    await flush_store(store)
    return result if isinstance(result, dict) else {"status": "failed"}


@activity.defn(name="research_exhausted")
@repository_activity(process_store)
async def research_exhausted(payload: dict[str, Any]) -> dict[str, str]:
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None:
        return {"status": "missing_store", "run_id": str(run_id)}
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.hydrate import reload_run  # noqa: PLC0415
    from ar_domain.research.driver import exhaust  # noqa: PLC0415

    await reload_run(store, run_id)
    run = _run(store, run_id)
    if run is None:
        return {"status": "missing", "run_id": str(run_id)}
    exhaust(store, run)
    await flush_store(store)
    return {"status": str(run.get("status") or "failed"), "run_id": str(run_id)}


@activity.defn(name="research_cancel")
@repository_activity(process_store)
async def research_cancel(payload: dict[str, Any]) -> dict[str, str]:
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    run = _run(store, run_id) if store is not None else None
    if isinstance(run, dict) and str(run.get("status") or "") not in {
        "completed",
        "failed",
        "cancelled",
    }:
        run["status"] = "cancelled"
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        await flush_store(store)
    return {"status": "cancelled", "run_id": str(run_id)}

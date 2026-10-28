"""RoutineRunWorkflow. Spec: docs/03-specs/15-routines-triggers.md §3."""

from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import uuid

    from ar_domain.durable.bind import binding_from
    from ar_domain.durable.flush import flush_store
    from ar_domain.durable.hydrate import hydrate_tenant, reload_run
    from ar_domain.routines.engine import (
        accept_routine_event,
        complete_routine_event,
        prepare_routine_run,
        reconcile_schedules,
    )
    from ar_system.routines_store import current_store


def _envelope(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


async def _refresh() -> Any:
    store: Any = current_store()
    binding = binding_from(store)
    if binding is not None and store.durable_engine is not None:
        await hydrate_tenant(store, store.durable_engine, binding.tenant_id)
    return store


@activity.defn(name="accept_routine_event")
async def accept_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = await _refresh()
    result = accept_routine_event(
        store,
        routine_id=uuid.UUID(str(payload["routine_id"])),
        source=str(payload.get("source") or "schedule"),
        idempotency_key=str(payload.get("idempotency_key") or workflow_key()),
        envelope=_envelope(payload.get("envelope")),
    )
    if result.get("status") == "duplicate":
        prior = store.routine_events.get(uuid.UUID(str(result["event_id"])), {})
        if prior.get("status") == "accepted":
            result["status"] = "accepted"
    await flush_store(store)
    return result


def workflow_key() -> str:
    return (activity.info().workflow_id or "manual") if activity.in_activity() else "manual"


@activity.defn(name="prepare_routine_run")
async def prepare_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = await _refresh()
    result = prepare_routine_run(
        store, uuid.UUID(str(payload["routine_id"])), uuid.UUID(str(payload["event_id"]))
    )
    await flush_store(store)
    return result


@activity.defn(name="complete_routine_event")
async def complete_activity(payload: dict[str, Any]) -> dict[str, Any]:
    store = await _refresh()
    event_id = uuid.UUID(str(payload["event_id"]))
    event = store.routine_events.get(event_id, {})
    run_id = event.get("run_id")
    if isinstance(run_id, uuid.UUID):
        await reload_run(store, run_id)
        if run_id in store.runs:
            store.runs[run_id]["dry_run"] = bool(event.get("dry_run"))
    if event.get("status") == "started":
        return {"status": str(payload.get("run_status") or "completed"), "event_id": str(event_id)}
    result = complete_routine_event(
        store, event_id, run_status=str(payload.get("run_status") or "completed")
    )
    await flush_store(store)
    return result


@activity.defn(name="reconcile_routine_schedules")
async def reconcile_activity() -> dict[str, int]:
    return reconcile_schedules(current_store())


@workflow.defn(name="RoutineRunWorkflow")
class RoutineRunWorkflow:
    """Accept an event, run the agent, then record delivery."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("event_id") and payload.get("run_id"):
            accepted = {"event_id": payload["event_id"]}
            prepared = {"run_id": payload["run_id"]}
        else:
            accepted = await workflow.execute_activity(
                accept_activity, payload, start_to_close_timeout=timedelta(seconds=30)
            )
            if not isinstance(accepted, dict) or accepted.get("status") != "accepted":
                return accepted if isinstance(accepted, dict) else {"status": "missing"}
            prepared = await workflow.execute_activity(
                prepare_activity,
                {"routine_id": payload["routine_id"], "event_id": accepted["event_id"]},
                start_to_close_timeout=timedelta(seconds=30),
            )
            if not isinstance(prepared, dict) or prepared.get("status") != "ready":
                return prepared if isinstance(prepared, dict) else {"status": "missing"}
        queue = str(payload.get("runtime_queue") or "ar-runtime")
        child = await workflow.execute_child_workflow(
            "AgentRunWorkflow",
            {
                "run_id": prepared["run_id"],
                "text": prepared.get("text") or "",
                "names": [],
            },
            id=f"run-{prepared['run_id']}",
            task_queue=queue,
        )
        status = "completed"
        if isinstance(child, dict) and child.get("status"):
            status = "completed" if child["status"] == "completed" else "failed"
        return await workflow.execute_activity(
            complete_activity,
            {"event_id": accepted["event_id"], "run_status": status},
            start_to_close_timeout=timedelta(seconds=30),
        )


@workflow.defn(name="RoutineReconcileWorkflow")
class RoutineReconcileWorkflow:
    """Hourly repair of Temporal schedule ids."""

    @workflow.run
    async def run(self) -> dict[str, int]:
        return await workflow.execute_activity(
            reconcile_activity,
            start_to_close_timeout=timedelta(seconds=30),
        )

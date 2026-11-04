"""In-process schedule ticks and live webhook runs.

Overlap defaults to skip: a fire while the previous run is still going is recorded
and does not start a second run. Queue (`buffer_one`) keeps one event and starts it
on the next tick after the active run finishes. A second event while one is queued
is skipped.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any  # noqa: TC003

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.routines.engine import (
    accept_routine_event,
    complete_routine_event,
    prepare_routine_run,
)

_SKIP = "Skipped because the previous run is still going."
_QUEUE_FULL = "Skipped because a run is already queued behind the one still going."
_QUEUED = "Queued behind the run that is still going. It starts when that run finishes."
_ACTIVE = {"queued", "running", "waiting_approval", "waiting_input"}


def wants_live(routine: dict[str, object]) -> bool:
    config = routine.get("trigger_config")
    return isinstance(config, dict) and config.get("execute_model") is True


def routine_for_token(store: Any, token: str) -> dict[str, object] | None:
    for row in store.routines.values():
        if isinstance(row, dict) and row.get("webhook_path_token") == token:
            return row
    return None


async def fire_schedule(
    store: Any, routine_id: uuid.UUID, *, force: bool = False
) -> dict[str, object]:
    """Start the due run, or record a skip or a queue."""
    routine = store.routines.get(routine_id)
    if not isinstance(routine, dict):
        return {"status": "missing"}
    if routine.get("status") != "active":
        return {"status": "paused", "message": "This schedule is paused."}
    if not force and not _due(routine):
        return {"status": "not_due", "message": "This schedule is not due yet."}
    queued = _queued_event(store, routine_id)
    if _active_count(store, routine_id):
        return _hold(store, routine, queued)
    if queued is not None:
        return await _start_existing(store, routine, queued)
    return await _start_new(store, routine, source="schedule")


async def drive_trigger(store: Any, run_id: uuid.UUID, text: str, event_id: uuid.UUID) -> None:
    await store.generate(run_id, text, [])
    run = store.runs.get(run_id)
    status = str(run.get("status") if isinstance(run, dict) else "failed")
    mapped = "failed" if status in {"failed", "budget_exceeded", "cancelled"} else "completed"
    complete_routine_event(store, event_id, run_status=mapped)


def _hold(
    store: Any, routine: dict[str, object], queued: dict[str, object] | None
) -> dict[str, object]:
    policy = str(routine.get("concurrency_policy") or "skip")
    if policy in {"queue", "buffer_one"} and queued is None:
        event = _insert_event(store, routine, "queued", _QUEUED)
        return {"status": "queued", "message": _QUEUED, "event_id": str(event["id"])}
    message = _QUEUE_FULL if policy in {"queue", "buffer_one"} else _SKIP
    event = _insert_event(store, routine, "skipped_concurrency", message)
    return {"status": "skipped_concurrency", "message": message, "event_id": str(event["id"])}


async def _start_new(store: Any, routine: dict[str, object], *, source: str) -> dict[str, object]:
    accepted = accept_routine_event(
        store,
        routine_id=_as_uuid(routine.get("id")),
        source=source,
        idempotency_key=f"{source}:{new_id()}",
        envelope={"type": source, "data": {}},
    )
    if accepted.get("status") != "accepted":
        message = (
            _SKIP
            if accepted.get("status") == "skipped_concurrency"
            else str(accepted.get("status"))
        )
        return {
            "status": accepted.get("status"),
            "message": message,
            "event_id": accepted.get("event_id"),
        }
    return await _prepare_and_run(store, routine, uuid.UUID(str(accepted["event_id"])))


async def _start_existing(
    store: Any, routine: dict[str, object], event: dict[str, object]
) -> dict[str, object]:
    event["status"] = "accepted"
    return await _prepare_and_run(store, routine, uuid.UUID(str(event["id"])))


async def _prepare_and_run(
    store: Any, routine: dict[str, object], event_id: uuid.UUID
) -> dict[str, object]:
    prepared = prepare_routine_run(store, _as_uuid(routine.get("id")), event_id)
    if prepared.get("status") != "ready":
        return {"status": prepared.get("status"), "message": str(prepared.get("status"))}
    run_id = uuid.UUID(str(prepared["run_id"]))
    text = str(prepared.get("text") or "")
    if wants_live(routine):
        await drive_trigger(store, run_id, text, event_id)
    else:
        run = store.runs[run_id]
        run["status"] = "completed"
        run["ended_at"] = utcnow()
        run["result_summary"] = text[:500] or "Schedule accepted."
        complete_routine_event(store, event_id)
    run = store.runs.get(run_id)
    status = str(run.get("status") if isinstance(run, dict) else "completed")
    return {"status": status, "run_id": str(run_id), "event_id": str(event_id)}


def _due(routine: dict[str, object]) -> bool:
    nxt = routine.get("next_run_at")
    if nxt is None:
        return True
    return isinstance(nxt, datetime) and nxt <= utcnow()


def _as_uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _active_count(store: Any, routine_id: object) -> int:
    return sum(
        1
        for run in store.runs.values()
        if isinstance(run, dict)
        and run.get("routine_id") == routine_id
        and run.get("status") in _ACTIVE
    )


def _queued_event(store: Any, routine_id: object) -> dict[str, object] | None:
    found = [
        row
        for row in store.routine_events.values()
        if isinstance(row, dict)
        and row.get("routine_id") == routine_id
        and row.get("status") == "queued"
    ]
    if not found:
        return None
    found.sort(key=lambda item: str(item.get("received_at")))
    return found[0]


def _insert_event(
    store: Any, routine: dict[str, object], status: str, message: str
) -> dict[str, object]:
    event_id = new_id()
    event = {
        "id": event_id,
        "tenant_id": routine.get("tenant_id"),
        "routine_id": routine.get("id"),
        "source": "schedule",
        "idempotency_key": f"schedule:{event_id}",
        "status": status,
        "detail": {"message": message},
        "received_at": utcnow(),
        "run_id": None,
        "envelope": {"type": "schedule", "data": {}},
    }
    store.routine_events[event_id] = event
    return event

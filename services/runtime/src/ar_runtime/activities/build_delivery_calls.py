"""Delivery calls constructed after a routine's final answer.

Spec: docs/03-specs/15-routines-triggers.md §4. These tools are never offered
to the model. Only a run with trigger ``routine`` receives them.
"""

from typing import TYPE_CHECKING

from ar_domain.routines.engine import deliver

if TYPE_CHECKING:
    import uuid


def build_delivery_calls(store: object, run_id: uuid.UUID) -> list[dict[str, object]]:
    """One call per delivery target on the routine that owns this run."""
    runs = getattr(store, "runs", {})
    routines = getattr(store, "routines", {})
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict) or run.get("trigger") != "routine":
        return []
    routine_id = run.get("routine_id")
    routine = routines.get(routine_id) if isinstance(routines, dict) else None
    if not isinstance(routine, dict):
        return []
    event = {
        "id": run.get("id"),
        "routine_id": routine_id,
    }
    return deliver(store, routine, event, run)

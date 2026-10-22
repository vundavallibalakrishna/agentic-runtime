"""Create one child run. The activity is idempotent for a parent id and index."""

from typing import Any  # noqa: TC003

from temporalio import activity

from ar_domain.skills.delegate import plan_child
from ar_runtime.activities.expire_approval import current_store


@activity.defn(name="create_child_run")
async def create_child_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Plan a child. A repeated call with the same index returns the same id."""
    planned = plan_child(payload)
    store = current_store()
    if store is None or planned.get("error"):
        return planned
    runs = getattr(store, "runs", None)
    if not isinstance(runs, dict):
        return planned
    child_id = str(planned.get("child_run_id") or "")
    if any(str(row.get("id")) == child_id for row in runs.values() if isinstance(row, dict)):
        return planned
    return planned

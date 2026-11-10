"""Suspend idle computers and destroy those past their lifetime.

The workflow is one activity. Repeating it is safe: a suspended computer stays
suspended and a terminated computer stays terminated.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from temporalio import activity, workflow

_STORE: Any = None


def bind_store(store: Any) -> None:
    """Point the reaper at the process store."""
    global _STORE  # noqa: PLW0603
    _STORE = store


@activity.defn(name="reap_sandboxes")
async def reap_sandboxes() -> dict[str, int]:
    """Idle suspend, max-lifetime destroy, and a no-op when nothing is due."""
    if _STORE is None:
        return {"suspended": 0, "terminated": 0}
    from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415
    from ar_domain.sandboxes.runtime import reap  # noqa: PLC0415

    if not isinstance(_STORE, RepositoryReadModel):
        return reap(_STORE)
    suspended = 0
    terminated = 0
    for tenant_id in await _STORE.tenant_ids():
        async with _STORE.open(tenant_id) as unit:
            part = reap(unit)
        suspended += int(part.get("suspended", 0))
        terminated += int(part.get("terminated", 0))
    return {"suspended": suspended, "terminated": terminated}


@workflow.defn
class SandboxReaperWorkflow:
    """Scheduled sweep. The activity owns the clocks."""

    @workflow.run
    async def run(self) -> dict[str, int]:
        result = await workflow.execute_activity(
            reap_sandboxes,
            start_to_close_timeout=timedelta(seconds=60),
        )
        if isinstance(result, dict):
            return {
                "suspended": int(result.get("suspended", 0)),
                "terminated": int(result.get("terminated", 0)),
            }
        return {"suspended": 0, "terminated": 0}

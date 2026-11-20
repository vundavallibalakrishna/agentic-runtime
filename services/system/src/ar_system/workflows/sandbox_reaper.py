"""Suspend idle computers, destroy those past their lifetime, remove orphaned containers.

The workflow is one activity, started by the schedule in ``ar_system.sandbox_schedule``.
Repeating it is safe: a suspended computer stays suspended, a terminated computer stays
terminated, and a container already removed is not an error.
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
    """One sweep: suspend the idle, end the expired, remove containers nobody owns.

    Where the install has a sandbox manager the sweep is asked of it, because the
    containers are there. A no-op when nothing is due.
    """
    if _STORE is None:
        return {"suspended": 0, "terminated": 0, "removed": 0}
    from ar_domain.documents.lifecycle import sweep_expired  # noqa: PLC0415
    from ar_domain.sandboxes.lifecycle import sweep  # noqa: PLC0415

    sweep_expired(_STORE)
    return await sweep(_STORE)


@workflow.defn
class SandboxReaperWorkflow:
    """Scheduled sweep. The activity owns the clocks."""

    @workflow.run
    async def run(self) -> dict[str, int]:
        result = await workflow.execute_activity(
            reap_sandboxes,
            start_to_close_timeout=timedelta(seconds=300),
        )
        counts = result if isinstance(result, dict) else {}
        return {key: int(counts.get(key, 0)) for key in ("suspended", "terminated", "removed")}

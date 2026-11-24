"""End runs that nothing is carrying out any more.

A working run belongs to its workflow, ``run-{id}``, which a worker carries out and which
ends the run itself when a step is lost. A process that starts therefore knows nothing
about a ``running`` row until it asks Temporal. It used to fail every one of them, so one
process restarting ended the runs every other process held (OQ-193).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any  # noqa: TC003

from ar_common.logging import get_logger
from ar_common.time import utcnow
from ar_domain.runs.failure import fail_run

_INTERRUPTED = (
    "The workflow that was carrying out this run is no longer running. The run was marked "
    "failed and was not resumed."
)
_ASK_TIMEOUT_S = 5.0
_log = get_logger(__name__)


async def reconcile_interrupted(store: Any) -> list[str]:
    """Fail each ``running`` run whose workflow Temporal says is gone. Return their ids.

    A run whose workflow is still going is left alone, whichever process holds it. So is
    every run when Temporal cannot be asked: not knowing is not a reason to end a run.
    Runs paused for a person are never touched.
    """
    changed: list[str] = []
    runs = getattr(store, "runs", {})
    gone = getattr(store, "_workflow_gone", None)
    if not isinstance(runs, dict) or not callable(gone):
        return changed
    working = [
        run
        for run in list(runs.values())
        if isinstance(run, dict) and run.get("status") == "running"
    ]
    if working and getattr(store, "temporal_client", None) is None:
        _log.warning("running_runs_not_checked", count=len(working), reason="no_temporal_client")
        return changed
    for run in working:
        try:
            asked = gone(uuid.UUID(str(run.get("id"))))
            lost = await asyncio.wait_for(asked, timeout=_ASK_TIMEOUT_S)
        except TimeoutError:
            lost = False
        if lost and run.get("status") == "running":
            _fail(store, run)
            changed.append(str(run.get("id")))
    return changed


def _fail(store: Any, run: dict[str, object]) -> None:
    fail_run(store, run, code="interrupted", message=_INTERRUPTED)
    audit = getattr(store, "audit_log", None)
    if isinstance(audit, list):
        audit.append(
            {
                "tenant_id": str(run.get("tenant_id")),
                "actor_id": "system",
                "action": "run.interrupted",
                "target_type": "run",
                "target_id": str(run.get("id")),
                "detail": {"code": "interrupted"},
                "outcome": "failure",
                "at": utcnow().isoformat(),
            }
        )

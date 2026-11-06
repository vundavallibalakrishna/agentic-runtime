"""Mark runs that were in flight when the process stopped."""

from __future__ import annotations

from typing import Any  # noqa: TC003

from ar_common.time import utcnow
from ar_domain.runs.failure import fail_run

_INTERRUPTED = (
    "The API restarted while this run was working. It was marked failed and was not resumed."
)


def reconcile_interrupted(store: Any) -> list[str]:
    """Fail `running` rows loaded from a previous process. Paused runs stay paused."""
    changed: list[str] = []
    runs = getattr(store, "runs", {})
    if not isinstance(runs, dict):
        return changed
    for run in list(runs.values()):
        if not isinstance(run, dict) or str(run.get("status")) != "running":
            continue
        _fail(store, run)
        changed.append(str(run.get("id")))
    from ar_domain.jobs.progress import mark_jobs_interrupted  # noqa: PLC0415

    mark_jobs_interrupted(store)
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

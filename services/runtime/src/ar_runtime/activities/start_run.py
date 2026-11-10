"""Check run quotas before a turn starts. Spec: docs/03-specs/17-audit-usage-metering.md §2.2."""

from __future__ import annotations

import uuid
from typing import Any  # noqa: TC003

from temporalio import activity

from ar_common.errors import QuotaExceededError
from ar_domain.readmodel.activity import repository_activity
from ar_domain.usage.service import UsageBook
from ar_runtime.activities.expire_approval import current_store, process_store


def assert_start(store: Any, run_id: uuid.UUID) -> None:
    """Raise ``QuotaExceededError`` when this run would pass a block quota."""
    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict):
        return
    tenant = run.get("tenant_id")
    user = run.get("user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return
    UsageBook(store).assert_run(tenant, user, run.get("agent_id"))


@activity.defn(name="start_run")
@repository_activity(process_store)
async def start_run(payload: dict[str, Any]) -> dict[str, str]:
    """Activity form of :func:`assert_start` for the runtime worker."""
    store = current_store()
    run_id = uuid.UUID(str(payload.get("run_id") or ""))
    if store is None:
        return {"status": "missing_store", "run_id": str(run_id)}
    try:
        assert_start(store, run_id)
    except QuotaExceededError as exc:
        _fail(store, run_id, str(exc))
        return {"status": "quota_exceeded", "run_id": str(run_id)}
    return {"status": "ok", "run_id": str(run_id)}


def _fail(store: Any, run_id: uuid.UUID, detail: str) -> None:
    from ar_domain.runs.failure import fail_run  # noqa: PLC0415

    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if isinstance(run, dict):
        fail_run(store, run, code="quota_exceeded", message=detail)

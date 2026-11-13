"""Optional Temporal worker build ids. Spec: docs/07-ops/ci-cd.md §6."""

import os
from typing import TypedDict


class WorkerVersioning(TypedDict, total=False):
    """Keyword arguments for ``temporalio.worker.Worker``."""

    build_id: str
    use_worker_versioning: bool


def temporal_worker_kwargs() -> WorkerVersioning:
    """Enable worker versioning only when the chart sets both variables.

    Local processes and tests leave the variables unset, so workers keep the
    previous polling behaviour.
    """
    build_id = os.environ.get("TEMPORAL_WORKER_BUILD_ID", "").strip()
    flag = os.environ.get("TEMPORAL_USE_WORKER_VERSIONING", "").strip().lower()
    if flag not in {"1", "true", "yes"} or not build_id:
        return {}
    return {"build_id": build_id, "use_worker_versioning": True}


def temporal_unavailable_fields(
    address: str, exc: BaseException, *, retry_in_s: int = 5
) -> dict[str, object]:
    """Log fields for a worker that cannot reach the Temporal frontend.

    The worker keeps the health server up and retries, so the log says where it tried, what
    went wrong and when it will try again, not only the exception's class name.
    """
    return {
        "message": f"Cannot reach the Temporal frontend at {address}; retrying in {retry_in_s}s.",
        "address": address,
        "error": type(exc).__name__,
        "detail": str(exc),
        "retry_in_s": retry_in_s,
    }

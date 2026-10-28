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

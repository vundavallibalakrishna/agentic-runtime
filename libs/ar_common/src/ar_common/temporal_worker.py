"""Options every Temporal worker starts with. Build ids: docs/07-ops/ci-cd.md §6."""

import os
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def temporal_worker_kwargs() -> dict[str, Any]:
    """The options every worker of the install is started with.

    Activities report to Temporal at most every ``AR_ACTIVITY_HEARTBEAT_THROTTLE_S``
    seconds. A stop is delivered with that report, so a short interval is what lets Stop
    interrupt a reply while it is being written.

    Worker versioning is on only when the chart sets both of its variables. Local
    processes and tests leave them unset, so workers keep the previous polling behaviour.
    """
    from ar_common.settings import get_settings  # noqa: PLC0415

    options: dict[str, Any] = {
        "max_heartbeat_throttle_interval": timedelta(
            seconds=get_settings().activity_heartbeat_throttle_s
        )
    }
    build_id = os.environ.get("TEMPORAL_WORKER_BUILD_ID", "").strip()
    flag = os.environ.get("TEMPORAL_USE_WORKER_VERSIONING", "").strip().lower()
    if flag in {"1", "true", "yes"} and build_id:
        options.update({"build_id": build_id, "use_worker_versioning": True})
    return options


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

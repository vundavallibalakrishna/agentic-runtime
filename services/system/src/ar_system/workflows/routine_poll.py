"""RoutinePollWorkflow. Spec: docs/03-specs/15-routines-triggers.md §6."""

from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import uuid

    from ar_domain.routines.engine import poll_routine_source
    from ar_system.routines_store import current_store


@activity.defn(name="poll_routine_source")
async def poll_activity(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return poll_routine_source(current_store(), uuid.UUID(str(payload["routine_id"])))


@workflow.defn(name="RoutinePollWorkflow")
class RoutinePollWorkflow:
    """List changes since the watermark and start at most 20 runs."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return await workflow.execute_activity(
            poll_activity,
            payload,
            start_to_close_timeout=timedelta(seconds=60),
        )

"""SourceSyncWorkflow. Spec: docs/03-specs/10-knowledge.md §4.1."""

from typing import Any  # noqa: TC003

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ar_ingest.activities import sync_source_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="SourceSyncWorkflow")
class SourceSyncWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            sync_source_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

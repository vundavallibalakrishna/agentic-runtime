"""SourceSyncWorkflow. Spec: docs/03-specs/10-knowledge.md §4.1."""

from typing import Any  # noqa: TC003

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ar_ingest.activities import sync_source_activity
from datetime import timedelta

from ar_ingest.workflows.common import RETRY


@workflow.defn(name="SourceSyncWorkflow")
class SourceSyncWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            sync_source_activity,
            payload,
            # A site of thousands of pages takes hours. The activity says it is alive as
            # each page is done, so one that stops is noticed in minutes, not hours.
            start_to_close_timeout=timedelta(hours=6),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=RETRY,
        )

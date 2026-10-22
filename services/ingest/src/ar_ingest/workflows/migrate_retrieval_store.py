"""MigrateRetrievalStoreWorkflow. Spec: docs/03-specs/10-knowledge.md §9."""

from temporalio import workflow

from ar_ingest.activities import migrate_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="MigrateRetrievalStoreWorkflow")
class MigrateRetrievalStoreWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        return await workflow.execute_activity(
            migrate_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

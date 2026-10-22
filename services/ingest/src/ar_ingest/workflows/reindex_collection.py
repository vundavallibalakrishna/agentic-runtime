"""ReindexCollectionWorkflow. Spec: docs/03-specs/10-knowledge.md §4.5."""

from temporalio import workflow

from ar_ingest.activities import reindex_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="ReindexCollectionWorkflow")
class ReindexCollectionWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        return await workflow.execute_activity(
            reindex_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

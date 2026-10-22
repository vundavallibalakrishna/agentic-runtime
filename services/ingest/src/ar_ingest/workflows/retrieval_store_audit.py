"""RetrievalStoreAuditWorkflow. Registered when a qdrant collection exists."""

from temporalio import workflow

from ar_ingest.activities import audit_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="RetrievalStoreAuditWorkflow")
class RetrievalStoreAuditWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        return await workflow.execute_activity(
            audit_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

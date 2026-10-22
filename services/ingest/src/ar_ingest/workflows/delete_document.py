"""DeleteDocumentWorkflow. Spec: docs/03-specs/10-knowledge.md §4.4."""

from temporalio import workflow

from ar_ingest.activities import delete_document_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="DeleteDocumentWorkflow")
class DeleteDocumentWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        return await workflow.execute_activity(
            delete_document_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

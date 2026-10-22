"""IngestDocumentWorkflow. Spec: docs/03-specs/10-knowledge.md §4.2."""

from temporalio import workflow

from ar_ingest.activities import ingest_document_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="IngestDocumentWorkflow")
class IngestDocumentWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        return await workflow.execute_activity(
            ingest_document_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

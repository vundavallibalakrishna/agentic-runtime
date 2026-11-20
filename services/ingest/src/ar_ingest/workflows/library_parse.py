"""Parse a staged library document on the ingest worker."""

from typing import Any  # noqa: TC003

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from ar_ingest.activities import parse_library_activity
from ar_ingest.workflows.common import RETRY, TIMEOUT


@workflow.defn(name="LibraryParseWorkflow")
class LibraryParseWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            parse_library_activity,
            payload,
            start_to_close_timeout=TIMEOUT,
            retry_policy=RETRY,
        )

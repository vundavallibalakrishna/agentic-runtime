"""ReindexCollectionWorkflow. Spec: docs/03-specs/10-knowledge.md §4.5.

Blue/green in steps: name the new version and its documents, write the documents into it
a batch at a time, then switch the collection to it and delete the old version. A step
that cannot finish ends the job as failed and leaves the old version in use.
"""

from datetime import timedelta
from typing import Any  # noqa: TC003

from temporalio import workflow
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from ar_ingest.activities import (
        reindex_abandon_activity,
        reindex_documents_activity,
        reindex_prepare_activity,
        reindex_switch_activity,
    )
from ar_ingest.workflows.common import RETRY, TIMEOUT

# Documents written by one activity. Each is parsed and embedded again, so a batch that
# is tried again repeats little, and the worker says it is alive after each document.
BATCH = 20


@workflow.defn(name="ReindexCollectionWorkflow")
class ReindexCollectionWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        version: int | None = None
        try:
            plan = await workflow.execute_activity(
                reindex_prepare_activity,
                payload,
                start_to_close_timeout=TIMEOUT,
                retry_policy=RETRY,
            )
            version = int(plan["version"])
            documents = list(plan.get("document_ids") or [])
            for start in range(0, len(documents), BATCH):
                await workflow.execute_activity(
                    reindex_documents_activity,
                    {
                        **payload,
                        "version": version,
                        "document_ids": documents[start : start + BATCH],
                    },
                    start_to_close_timeout=timedelta(hours=1),
                    heartbeat_timeout=timedelta(minutes=5),
                    retry_policy=RETRY,
                )
            return await workflow.execute_activity(
                reindex_switch_activity,
                {**payload, "version": version},
                start_to_close_timeout=timedelta(hours=1),
                heartbeat_timeout=timedelta(minutes=5),
                retry_policy=RETRY,
            )
        except ActivityError as exc:
            return await workflow.execute_activity(
                reindex_abandon_activity,
                {**payload, "version": version, "error": _reason(exc)},
                start_to_close_timeout=TIMEOUT,
                retry_policy=RETRY,
            )


def _reason(exc: ActivityError) -> str:
    cause = exc.cause
    if isinstance(cause, ApplicationError) and cause.message:
        return str(cause.message)
    return f"the re-index stopped ({type(cause or exc).__name__})"

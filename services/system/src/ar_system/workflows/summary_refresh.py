"""Refresh one conversation summary. The row is committed with the activity."""

from datetime import timedelta
from typing import Any  # noqa: TC003 - Temporal inspects the payload annotation

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import uuid

    from ar_domain.conversations.summary import refresh_summary
    from ar_domain.readmodel.activity import repository_activity
    from ar_system.routines_store import current_store, process_store


@activity.defn(name="refresh_conversation_summary")
@repository_activity(process_store)
async def refresh_conversation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    store = current_store()
    tenant_id = uuid.UUID(str(payload["tenant_id"]))
    conversation_id = uuid.UUID(str(payload["conversation_id"]))
    found = refresh_summary(store, tenant_id, conversation_id)
    return {str(key): value for key, value in found.items()}


@workflow.defn(name="ConversationSummaryWorkflow")
class ConversationSummaryWorkflow:
    """One activity folds the conversation and stores the summary."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            refresh_conversation_summary,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
        )

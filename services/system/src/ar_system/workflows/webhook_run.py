"""Run one webhook delivery on the system worker."""

from datetime import timedelta
from typing import Any  # noqa: TC003 — Temporal reads annotations at runtime

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    import uuid

    from ar_domain.readmodel.activity import repository_activity
    from ar_domain.webhooks.delivery import attempt
    from ar_system.routines_store import current_store, process_store


@activity.defn(name="deliver_webhook")
@repository_activity(process_store)
async def deliver_webhook_activity(payload: dict[str, Any]) -> dict[str, Any]:
    delivery_id = uuid.UUID(str(payload.get("delivery_id") or ""))
    return attempt(current_store(), delivery_id)


@workflow.defn(name="WebhookDeliveryWorkflow")
class WebhookDeliveryWorkflow:
    """POST, then wait out the shared backoff until the delivery finishes."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        while True:
            result = await workflow.execute_activity(
                deliver_webhook_activity,
                payload,
                start_to_close_timeout=timedelta(seconds=30),
            )
            wait = result.get("retry_in_s") if isinstance(result, dict) else None
            if not isinstance(wait, int):
                return result if isinstance(result, dict) else {"status": "failed"}
            await workflow.sleep(timedelta(seconds=wait))

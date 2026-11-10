"""SMTP delivery for one notice. Retry and backoff belong to the activity."""

from datetime import timedelta
from typing import Any  # noqa: TC003 - Temporal inspects the payload annotation

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from ar_domain.notifications.smtp_mail import send_smtp


@activity.defn(name="send_smtp_notification")
async def send_smtp_notification(payload: dict[str, Any]) -> dict[str, Any]:
    """Send one message. A refused attempt raises so Temporal retries it."""
    send_smtp(payload)
    attempt = activity.info().attempt
    return {"sent": True, "attempts": attempt, "proof": "contract"}


@workflow.defn(name="NotificationEmailWorkflow")
class NotificationEmailWorkflow:
    """One activity sends the message. The retry policy backs off."""

    @workflow.run
    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await workflow.execute_activity(
            send_smtp_notification,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(milliseconds=200),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(seconds=5),
                maximum_attempts=4,
            ),
        )

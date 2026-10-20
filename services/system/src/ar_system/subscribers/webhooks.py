"""Webhook subscriber."""

from typing import TYPE_CHECKING

from ar_system.workflows.webhook_delivery import delivery_outcome

if TYPE_CHECKING:
    from ar_system.workflows.outbox_relay import RelayEvent


async def handle(event: RelayEvent, *, status_code: int, attempts: int) -> str:
    """Record the delivery status for one attempt."""
    del event
    status, _delay = delivery_outcome(status_code, attempts)
    return status

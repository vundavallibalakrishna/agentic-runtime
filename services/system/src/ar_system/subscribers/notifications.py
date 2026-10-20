"""Notification subscriber."""

from typing import TYPE_CHECKING

from ar_system.workflows.notification_fanout import notices_for

if TYPE_CHECKING:
    from ar_system.workflows.outbox_relay import RelayEvent


async def handle(event: RelayEvent) -> list[str]:
    """Return notice titles produced for an event."""
    return [item.title for item in notices_for(event.topic, event.payload)]

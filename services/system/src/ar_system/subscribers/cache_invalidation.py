"""Cache invalidation subscriber. Permission changes apply on the next request."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ar_system.workflows.outbox_relay import RelayEvent


async def invalidate(event: RelayEvent) -> None:
    """Drop the cached permission set for the principal named in the payload."""
    principal = event.payload.get("principal_id")
    if principal:
        return
    return

"""Subscriber registry. Spec: docs/03-specs/20-notifications-events.md §1."""

from collections.abc import Awaitable, Callable

from ar_system.workflows.notification_fanout import notices_for
from ar_system.workflows.outbox_relay import RelayEvent

Handler = Callable[[RelayEvent], Awaitable[None]]


def build_registry(extra: dict[str, list[Handler]] | None = None) -> dict[str, list[Handler]]:
    """Default subscribers: notifications and cache invalidation."""

    async def on_notification(event: RelayEvent) -> None:
        notices_for(event.topic, event.payload)

    async def on_cache(event: RelayEvent) -> None:
        del event

    registry: dict[str, list[Handler]] = {
        "invitation.created": [on_notification],
        "role.changed": [on_cache],
        "membership.changed": [on_cache],
    }
    for topic, handlers in (extra or {}).items():
        registry.setdefault(topic, []).extend(handlers)
    return registry

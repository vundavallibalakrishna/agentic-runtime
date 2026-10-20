"""Outbox relay. Spec: docs/03-specs/20-notifications-events.md §1."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

CONTINUE_AFTER = 1000


@dataclass
class RelayEvent:
    id: str
    topic: str
    payload: dict[str, object]
    attempts: int = 0


Subscriber = Callable[[RelayEvent], Awaitable[None]]


async def relay_once(
    events: list[RelayEvent],
    subscribers: dict[str, list[Subscriber]],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Dispatch one claimed batch. Returns published ids and (id, error) failures."""
    published: list[str] = []
    failed: list[tuple[str, str]] = []
    for event in events:
        handlers = subscribers.get(event.topic, []) + subscribers.get("*", [])
        try:
            for handler in handlers:
                await handler(event)
        except Exception as exc:  # noqa: BLE001 - one subscriber must not stop the batch
            failed.append((event.id, str(exc)))
            continue
        published.append(event.id)
    return published, failed


def should_continue_as_new(processed: int) -> bool:
    return processed >= CONTINUE_AFTER

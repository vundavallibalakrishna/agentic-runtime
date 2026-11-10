"""Optional callbacks a loaded pack may register. Core does not import a pack."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

PublishHook = Callable[[Any, Any, Any, Any], None]
ReviewHook = Callable[[Any, Any, Any], Any]

_publish: list[PublishHook] = []
_review: list[ReviewHook] = []


def register_publish_hook(fn: PublishHook) -> None:
    if fn not in _publish:
        _publish.append(fn)


def notify_published(store: Any, actor: Any, agent: Any, version: Any) -> None:
    for fn in _publish:
        fn(store, actor, agent, version)


def register_review_hook(fn: ReviewHook) -> None:
    if fn not in _review:
        _review.append(fn)


def review_delivery(store: Any, routine: Any, target: Any) -> Any:
    for fn in _review:
        waiting = fn(store, routine, target)
        if waiting is not None:
            return waiting
    return None

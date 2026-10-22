"""Dicts that remember which rows a request changed."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class TrackedList(list[object]):
    """A list whose mutations mark the parent row dirty."""

    def __init__(self, bucket: Any, key: object, items: list[object]) -> None:
        super().__init__(items)
        self._bucket = bucket
        self._key = key

    def _touch(self) -> None:
        self._bucket.touch(self._key)

    def append(self, item: object) -> None:
        super().append(item)
        self._touch()

    def extend(self, items: object) -> None:
        super().extend(items)  # type: ignore[arg-type]
        self._touch()

    def __setitem__(self, index: object, value: object) -> None:
        super().__setitem__(index, value)  # type: ignore[index, assignment]
        self._touch()

    def pop(self, index: int = -1) -> object:
        found = super().pop(index)
        self._touch()
        return found


class TrackedRow(dict[str, object]):
    """A row dict. Field writes mark the bucket key dirty."""

    def __init__(self, bucket: Any, key: object, data: dict[object, object]) -> None:
        super().__init__()
        self._bucket = bucket
        self._key = key
        for name, value in data.items():
            super().__setitem__(str(name), _wrap(bucket, key, value))
        bucket.touch(key)

    def __setitem__(self, key: str, value: object) -> None:
        super().__setitem__(key, _wrap(self._bucket, self._key, value))
        self._bucket.touch(self._key)


class TrackedDict(dict[object, object]):
    """``store.<bucket>`` replacement. Assignment records the key."""

    def __init__(self, store: Any, kind: str) -> None:
        super().__init__()
        self.store = store
        self.kind = kind
        self.dirty: set[object] = set()

    def touch(self, key: object) -> None:
        if not getattr(self.store, "reloading", False):
            self.dirty.add(key)

    def __setitem__(self, key: object, value: object) -> None:
        if isinstance(value, list):
            stored: object = (
                value if isinstance(value, TrackedList) else TrackedList(self, key, value)
            )
            super().__setitem__(key, stored)
        elif isinstance(value, dict):
            stored = value if isinstance(value, TrackedRow) else TrackedRow(self, key, value)
            super().__setitem__(key, stored)
        else:
            super().__setitem__(key, value)
        self.touch(key)

    def __delitem__(self, key: object) -> None:
        super().__delitem__(key)
        self.touch(key)

    def pop(self, key: object, default: object = None) -> object:
        found = super().pop(key, default)
        self.touch(key)
        return found


def _wrap(bucket: Any, key: object, value: object) -> object:
    if isinstance(value, dict) and not isinstance(value, TrackedRow):
        nested = TrackedRow(bucket, key, {})
        for name, item in value.items():
            nested[str(name)] = item
        return nested
    if isinstance(value, list) and not isinstance(value, TrackedList):
        return TrackedList(bucket, key, list(value))
    return value


BUCKETS = (
    "agents",
    "versions",
    "conversations",
    "messages",
    "runs",
    "events",
    "skills",
    "skill_versions",
    "memory_facts",
    "knowledge_collections",
    "knowledge_sources",
    "knowledge_documents",
    "document_chunks",
    "tool_servers",
    "tool_server_versions",
    "tool_defs",
    "tool_versions",
)


def install_tracking(store: Any) -> None:
    """Replace product dicts so later writes can be flushed."""
    for name in BUCKETS:
        current = getattr(store, name, None)
        if isinstance(current, TrackedDict):
            continue
        if not isinstance(current, dict):
            continue
        tracked = TrackedDict(store, name)
        store.reloading = True
        try:
            for key, value in current.items():
                tracked[key] = value
        finally:
            store.reloading = False
        tracked.dirty.clear()
        setattr(store, name, tracked)

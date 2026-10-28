"""Process-store buckets for records. HTTP reads these until a flush bucket exists."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def bucket(store: Any, name: str) -> dict[object, dict[str, object]]:
    """Return one named map on ``store.records``, creating it when missing."""
    root = getattr(store, "records", None)
    if not isinstance(root, dict):
        root = {}
        store.records = root
    current = root.get(name)
    if not isinstance(current, dict):
        current = {}
        root[name] = current
    return current


def blobs(store: Any, name: str) -> dict[object, bytes]:
    """Byte objects kept beside the row maps."""
    root = getattr(store, "records", None)
    if not isinstance(root, dict):
        root = {}
        store.records = root
    key = f"{name}_bytes"
    current = root.get(key)
    if not isinstance(current, dict):
        current = {}
        root[key] = current
    return current

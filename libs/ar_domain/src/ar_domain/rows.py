"""Narrow values stored on the in-process catalogue."""

import uuid
from datetime import datetime
from typing import cast


def as_int(value: object, default: int = 0) -> int:
    """Return an int, or ``default`` when the stored value is something else."""
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def as_uuid(value: object) -> uuid.UUID:
    """Return a UUID stored either as a UUID or as text."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def as_uuid_or_none(value: object) -> uuid.UUID | None:
    """Return a UUID, or None when the cell is empty."""
    if isinstance(value, uuid.UUID):
        return value
    if value is None or value == "":
        return None
    return uuid.UUID(str(value))


def as_dict(value: object) -> dict[str, object]:
    """Return a mapping, or an empty one."""
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return {}


def as_list(value: object) -> list[object]:
    """Return a list, or an empty one."""
    if isinstance(value, list):
        return cast("list[object]", value)
    return []


def as_datetime(value: object) -> datetime | None:
    """Return a datetime when that is what was stored."""
    if isinstance(value, datetime):
        return value
    return None

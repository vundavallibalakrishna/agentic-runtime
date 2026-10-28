"""Row helpers for the durable flush. Content stays out of logs."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import orjson

if TYPE_CHECKING:
    from typing import Any


def as_uuid(value: object) -> uuid.UUID | None:
    """Return a UUID, or None when the value is not one."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def as_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def as_bool(value: object) -> bool:
    return bool(value)


def as_dt(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def as_json(value: object, default: object) -> str:
    """JSON text for a jsonb bind value."""
    payload = value if isinstance(value, (dict, list)) else default
    return orjson.dumps(payload).decode()


def as_vector(value: object) -> str | None:
    """pgvector literal. A vector of the wrong length is omitted."""
    if not isinstance(value, list) or len(value) != 1024:
        return None
    numbers: list[str] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        numbers.append(str(float(item)))
    return "[" + ",".join(numbers) + "]"


def row_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def vector_values(value: object) -> list[float]:
    """Text queries may return pgvector's JSON-shaped string instead of an array."""
    if isinstance(value, str):
        try:
            value = orjson.loads(value)
        except orjson.JSONDecodeError:
            return []
    if not isinstance(value, (list, tuple)):
        return []
    return [
        float(item)
        for item in value
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    ]

"""Small parsers shared by the workflow modules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ar_common.errors import ValidationFailedError

if TYPE_CHECKING:
    from typing import Any


def required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationFailedError(f"{field} is required")
    return text


def choice(value: object, allowed: frozenset[str], field: str) -> str:
    picked = str(value or "")
    if picked not in allowed:
        raise ValidationFailedError(f"{field} is invalid")
    return picked


def scale(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValidationFailedError("score factors are 1 to 5")
    try:
        number = int(value)
    except ValueError as exc:
        raise ValidationFailedError("score factors are 1 to 5") from exc
    if number < 1 or number > 5:
        raise ValidationFailedError("score factors are 1 to 5")
    return number


def when(value: object, *, required: bool = False) -> datetime | None:
    if value is None or value == "":
        if required:
            raise ValidationFailedError("time is required")
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationFailedError("time is invalid") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def as_uuid(value: object, *, required: bool = True) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if value is None or value == "":
        if required:
            raise ValidationFailedError("id is required")
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        if required:
            raise ValidationFailedError("id is required") from exc
        return None


def string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationFailedError("a list is required")
    return [str(item) for item in value if str(item).strip()]


def mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}

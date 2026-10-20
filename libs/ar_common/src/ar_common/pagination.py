"""HMAC-signed opaque pagination cursors. Spec: docs/05-contracts/api-conventions.md §4."""

import base64
import hashlib
import hmac
from typing import TYPE_CHECKING, Literal

import orjson

from ar_common.errors import InvalidCursorError
from ar_common.jcs import canonical_json

if TYPE_CHECKING:
    from pydantic import JsonValue


def encode_cursor(
    keys: list[JsonValue],
    *,
    direction: Literal["asc", "desc"],
    secret: str,
) -> str:
    """Return an opaque cursor for the sort-key values of the last row."""
    payload = canonical_json({"k": keys, "d": direction})
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return _b64(payload) + "." + _b64(signature)


def decode_cursor(cursor: str, *, secret: str) -> tuple[list[JsonValue], Literal["asc", "desc"]]:
    """Verify a cursor and return ``(sort keys, direction)``.

    Raises:
        InvalidCursorError: the cursor is malformed or the signature does not match.
    """
    parts = cursor.split(".")
    if len(parts) != 2:
        raise InvalidCursorError
    try:
        payload = _b64decode(parts[0])
        signature = _b64decode(parts[1])
    except ValueError as exc:
        raise InvalidCursorError from exc
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise InvalidCursorError
    try:
        decoded = orjson.loads(payload)
    except orjson.JSONDecodeError as exc:
        raise InvalidCursorError from exc
    if not isinstance(decoded, dict) or "k" not in decoded or "d" not in decoded:
        raise InvalidCursorError
    direction = decoded["d"]
    keys = decoded["k"]
    if direction not in ("asc", "desc") or not isinstance(keys, list):
        raise InvalidCursorError
    return keys, direction


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)

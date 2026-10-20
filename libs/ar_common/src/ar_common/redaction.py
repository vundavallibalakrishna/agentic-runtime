"""Strip secrets and message content from audit detail and logs.

Spec: docs/03-specs/17-audit-usage-metering.md §1.1, docs/06-security/audit.md.
"""

import re
from typing import TypeVar

_SECRET_KEY = re.compile(
    r"(password|secret|token|api_key|authorization|cookie|private_key|credential|dsn)",
    re.IGNORECASE,
)
_CONTENT_KEY = re.compile(
    r"^(message|messages|content|body|prompt|completion|arguments|result|text)$",
    re.IGNORECASE,
)
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_ARK = re.compile(r"ark_[A-Za-z0-9]+")
_MAX_STRING = 500

T = TypeVar("T")


def redact(value: object) -> object:
    """Return a JSON-safe copy with secrets and message content removed."""
    return _walk(value)


def _walk(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            name = str(key)
            if _SECRET_KEY.search(name) or _CONTENT_KEY.search(name):
                cleaned[name] = "[redacted]"
            else:
                cleaned[name] = _walk(item)
        return cleaned
    if isinstance(value, list):
        return [_walk(item) for item in value]
    if isinstance(value, str):
        clipped = value[:_MAX_STRING]
        clipped = _BEARER.sub("Bearer [redacted]", clipped)
        return _ARK.sub("ark_[redacted]", clipped)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:_MAX_STRING]

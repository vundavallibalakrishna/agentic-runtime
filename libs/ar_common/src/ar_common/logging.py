"""Structured JSON logging. Spec: docs/03-specs/18-observability-eval.md §1."""

import hashlib
import logging
import re
from typing import TYPE_CHECKING, cast

import orjson
import structlog
from opentelemetry import trace

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from ar_common.settings import BaseServiceSettings

_SECRET_KEY = re.compile(
    r"(password|secret|token|api_key|authorization|cookie|private_key|credential)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


class _LogState:
    configured = False


def _orjson_dumps(value: object, **kwargs: object) -> str:
    del kwargs
    return orjson.dumps(value).decode("utf-8")


def _scrub(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if _SECRET_KEY.search(str(key)):
                cleaned[str(key)] = "[redacted]"
            else:
                cleaned[str(key)] = _scrub(item)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, str) and _BEARER.search(value):
        return _BEARER.sub("Bearer [redacted]", value)
    return value


def _scrub_secrets(
    _logger: object, _method: str, event_dict: MutableMapping[str, object]
) -> MutableMapping[str, object]:
    scrubbed = _scrub(dict(event_dict))
    return cast("MutableMapping[str, object]", scrubbed)


def _add_trace_ids(
    _logger: object, _method: str, event_dict: MutableMapping[str, object]
) -> MutableMapping[str, object]:
    span = trace.get_current_span()
    context = span.get_span_context()
    if context.is_valid:
        event_dict["trace_id"] = f"{context.trace_id:032x}"
        event_dict["span_id"] = f"{context.span_id:016x}"
    return event_dict


def _hash_user(value: object) -> str:
    raw = str(value).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def setup_logging(settings: BaseServiceSettings) -> None:
    """Configure structlog JSON logging for this process. Safe to call once."""
    if _LogState.configured:
        return

    def hash_user_ids(
        _logger: object, _method: str, event_dict: MutableMapping[str, object]
    ) -> MutableMapping[str, object]:
        if settings.log_hash_user_ids and "user_id" in event_dict:
            event_dict["user_id"] = _hash_user(event_dict["user_id"])
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_trace_ids,
            hash_user_ids,
            _scrub_secrets,
            structlog.processors.JSONRenderer(serializer=_orjson_dumps),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    _LogState.configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger. Call :func:`setup_logging` at process start."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))

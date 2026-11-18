"""Timeout, fallback and context-window policy for one chat completion.

The numbers come from the install catalogue (``AR_MG_MAX_FALLBACKS``,
``AR_MG_FALLBACK_BACKOFF_S``). A provider name never selects a branch.
"""

from __future__ import annotations

import os
import re

_CONTEXT = re.compile(
    r"context[_ ]length|maximum context|context window|too many tokens|context_length_exceeded",
    re.IGNORECASE,
)
_FORMAT = re.compile(r"response_format|json_schema|response format", re.IGNORECASE)


def max_fallback_hops() -> int:
    """How many fallback models may be tried after the primary. Default 2."""
    return _non_negative("AR_MG_MAX_FALLBACKS", 2)


def fallback_backoff_s(attempt: int) -> float:
    """Seconds to wait before fallback ``attempt`` (1 is the first retry)."""
    base = _positive_float("AR_MG_FALLBACK_BACKOFF_S", 0.2)
    return base * max(1, attempt)


def clamp_timeout(configured: float, budget_s: float | None) -> float:
    """``min(configured per-call timeout, remaining run budget)``.

    ``None`` leaves the configured timeout alone. A spent budget is ``0`` so
    the caller does not open a request.
    """
    if budget_s is None:
        return configured
    if budget_s <= 0:
        return 0.0
    return min(configured, budget_s)


def context_length_error(status: int, body: str) -> bool:
    """True when the provider rejected the call because the prompt did not fit."""
    if status not in {400, 413, 422}:
        return False
    return _CONTEXT.search(body) is not None


def response_format_rejected(status: int, body: str) -> bool:
    """True when a 400 names ``response_format`` so the caller can retry without it."""
    return status == 400 and _FORMAT.search(body) is not None


def _non_negative(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default

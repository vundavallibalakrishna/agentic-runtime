"""Scoring, guards and limits for memory facts. Spec: docs/03-specs/11-memory.md §2-§3."""

import math
import os
import re
from typing import TYPE_CHECKING

from ar_common.vectors import lexical_score

if TYPE_CHECKING:
    from datetime import datetime

_SECRET = re.compile(
    r"(?i)(password\s*[:=]|api[_-]?key\s*[:=]|secret\s*[:=]|bearer\s+\S+|ark_[A-Za-z0-9]+|"
    r"-----BEGIN [A-Z ]+-----)"
)
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_ACCOUNT = re.compile(
    r"(?i)\b(account number|iban|aadhaar|ssn|social security|routing number)\b\s*[:=]?\s*\d"
)
_SENSITIVE = re.compile(
    r"(?i)\b(my religion|my caste|sexual orientation|biometric|blood type|"
    r"medical record|diagnosis|prescription)\b"
)
_CATEGORIES = frozenset({"preference", "fact", "instruction", "lesson", "contact", "glossary"})
_USER_SCOPES = frozenset({"user", "agent_user"})
_STANDING = frozenset({"preference", "instruction"})
USER_FACT_LIMIT = 2000
SHARED_FACT_LIMIT = 5000
CONTENT_LIMIT = 500
MIN_CONFIDENCE = 0.7
TOKEN_BUDGET = 1500
DEFAULT_TOP_K = 8


def min_similarity() -> float:
    """``AR_MEMORY_RECALL_MIN_SIM``, default 0.25."""
    return _float_env("AR_MEMORY_RECALL_MIN_SIM", 0.25)


def dedupe_similarity() -> float:
    """``AR_MEMORY_DEDUPE_SIM``, default 0.92."""
    return _float_env("AR_MEMORY_DEDUPE_SIM", 0.92)


def dimensions() -> int:
    """``AR_PGVECTOR_DIMENSIONS``, fixed at 1024 for memory."""
    raw = os.environ.get("AR_PGVECTOR_DIMENSIONS", "1024")
    try:
        value = int(raw)
    except ValueError:
        return 1024
    return value if value > 0 else 1024


def lexical_blend() -> bool:
    """Fake embeddings are not semantic. Blend lexical overlap until a gateway is set."""
    return not os.environ.get("AR_MODEL_GATEWAY_URL", "").strip()


def score(cosine: float, *, age_days: float, recall_count: int) -> float:
    """``0.75 * cosine + 0.15 * exp(-age/90) + 0.10 * min(1, recalls/10)``."""
    freshness = math.exp(-max(age_days, 0.0) / 90)
    habit = min(1.0, max(recall_count, 0) / 10)
    return 0.75 * cosine + 0.15 * freshness + 0.10 * habit


def cosine(left: list[float], right: list[float]) -> float:
    """Dot product. Both vectors are unit length when they come from the embedder."""
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def similarity(query: str, content: str, query_vec: list[float], stored: object) -> float:
    """Cosine, or the larger of cosine and lexical overlap when embeddings are fake."""
    vector = stored if isinstance(stored, list) else []
    dense = cosine(query_vec, [float(item) for item in vector])
    if not lexical_blend():
        return dense
    return max(dense, lexical_score(query, content))


def blocked_reason(content: str, *, explicit: bool) -> str | None:
    """Secrets are never stored. Sensitive categories need an explicit request."""
    if _SECRET.search(content) or _CARD.search(content):
        return "secret"
    if explicit:
        return None
    if _ACCOUNT.search(content) or _SENSITIVE.search(content):
        return "sensitive"
    return None


def normalise(content: str) -> str:
    """Comparison key for exact duplicates."""
    return " ".join(content.lower().split())


def category_of(value: object, *, default: str = "fact") -> str:
    text = str(value or default)
    if text not in _CATEGORIES:
        return ""
    return text


def age_days(created_at: datetime, now: datetime) -> float:
    delta = now - created_at
    return max(delta.total_seconds(), 0.0) / 86400


def estimate_fact_tokens(content: str) -> int:
    """Rough budget for one fact line inside the memory block."""
    return max(1, len(content) // 4 + 8)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default

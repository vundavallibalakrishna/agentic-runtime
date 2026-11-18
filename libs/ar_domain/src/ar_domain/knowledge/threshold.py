"""The score a retrieved chunk must clear before it can be cited.

The agent sets ``knowledge.minScore``. A tenant setting of the same name is the
fallback, then the install setting ``AR_KNOWLEDGE_MIN_SCORE``. Unset means the
rerank model's own floor when a reranker is configured, and no numeric bar when
it is not. A chunk with no rerank score and no dense similarity does not clear
a numeric bar.
"""

from __future__ import annotations

import uuid

LIBRARY_MISS = "The library does not contain the answer to this question."


def retrieval_bar(store: object, tenant_id: object, definition: dict[str, object]) -> float | None:
    """The configured minimum, or ``None`` when nobody set one."""
    knowledge = definition.get("knowledge")
    chosen = _unit(knowledge.get("min_score") if isinstance(knowledge, dict) else None)
    if chosen is None and isinstance(tenant_id, uuid.UUID):
        settings = getattr(store, "tenant_settings", {})
        row = settings.get(tenant_id) if isinstance(settings, dict) else None
        section = row.get("knowledge") if isinstance(row, dict) else None
        if isinstance(section, dict):
            chosen = _unit(section.get("min_score", section.get("minScore")))
    if chosen is None:
        from ar_common.settings import get_settings  # noqa: PLC0415

        chosen = _unit(get_settings().knowledge_min_score)
    return chosen


def clears(hit: dict[str, object], bar: float | None) -> bool:
    """True when ``hit`` may be shown. No bar keeps the search order."""
    if bar is None:
        return True
    score = _hit_score(hit)
    return score is not None and score >= bar


def _hit_score(hit: dict[str, object]) -> float | None:
    """A 0-1 relevance score. Reciprocal-rank fusion is not one."""
    for key in ("rerank_score", "similarity"):
        raw = hit.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            continue
        return float(raw)
    return None


def _unit(raw: object) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    value = float(raw)
    if 0.0 <= value <= 1.0:
        return value
    return None

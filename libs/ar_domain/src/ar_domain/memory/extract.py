"""Turn text into memory operations. Spec: docs/03-specs/11-memory.md §4."""

import re

import orjson

from ar_domain.memory.logic import CONTENT_LIMIT, category_of

_REMEMBER = re.compile(r"(?i)(?:please\s+)?remember that\s+(.+?)(?:\.|$)")
_PREFER = re.compile(r"(?i)\bi prefer\s+(.+?)(?:\.|$)")
_OPS = frozenset({"add", "update", "delete", "noop"})
_SCOPES = frozenset({"user", "agent_user"})


def extraction_input(user_text: str, assistant_text: str) -> str:
    """Only the person's words and the final answer. Tool output stays out."""
    parts = [part.strip() for part in (user_text, assistant_text) if part.strip()]
    return "\n".join(parts)


def parse_ops(raw: str) -> list[dict[str, object]]:
    """Read a JSON list from a model response. Anything else is no operations."""
    start = raw.find("[")
    end = raw.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        parsed = orjson.loads(raw[start : end + 1])
    except orjson.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    ops: list[dict[str, object]] = []
    for item in parsed[:5]:
        if isinstance(item, dict):
            cleaned = _clean_op(item)
            if cleaned is not None:
                ops.append(cleaned)
    return ops


def heuristic_ops(user_text: str) -> list[dict[str, object]]:
    """Explicit phrases when the model does not return JSON."""
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for match in _REMEMBER.finditer(user_text):
        _add_phrase(found, seen, match.group(1), explicit=True)
    for match in _PREFER.finditer(user_text):
        phrase = match.group(1).strip()
        if any(phrase.lower() in str(item.get("content", "")).lower() for item in found):
            continue
        _add_phrase(found, seen, f"Prefers {phrase}", explicit=True)
    return found[:5]


def _add_phrase(
    found: list[dict[str, object]], seen: set[str], raw: str, *, explicit: bool
) -> None:
    content = " ".join(raw.split())[:CONTENT_LIMIT]
    if not content:
        return
    key = content.lower()
    if key in seen:
        return
    seen.add(key)
    category = "preference" if "prefer" in content.lower() else "fact"
    found.append(
        {
            "op": "add",
            "content": content,
            "category": category,
            "scope": "user",
            "confidence": 0.95 if explicit else 0.8,
            "explicit": explicit,
        }
    )


def _clean_op(item: dict[str, object]) -> dict[str, object] | None:
    op = str(item.get("op") or "")
    if op not in _OPS:
        return None
    scope = str(item.get("scope") or "user")
    if scope not in _SCOPES:
        scope = "user"
    category = category_of(item.get("category")) or "fact"
    content = " ".join(str(item.get("content") or "").split())[:CONTENT_LIMIT]
    confidence = item.get("confidence")
    score = float(confidence) if isinstance(confidence, (int, float)) else 0.0
    score = min(1.0, max(0.0, score))
    return {
        "op": op,
        "content": content,
        "category": category,
        "scope": scope,
        "target_fact_id": item.get("target_fact_id") or item.get("targetFactId"),
        "confidence": score,
        "explicit": bool(item.get("explicit")),
    }

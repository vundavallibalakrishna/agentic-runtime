"""Turn one question into a few search queries before the passages are fetched.

The model's own alias, or its quick alias, writes the queries. There is no list of
topics and no keyword rule. When the model is not connected, or its reply is not a
short list of queries, the search uses the question as it was asked.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson

from ar_common.wrapping import wrap_untrusted

if TYPE_CHECKING:
    from typing import Any

_MAX_QUERIES = 4
_TASK = (
    "Rewrite the question into one to four short search queries that would find the "
    "passages needed to answer every part of it. Use the earlier turns only to resolve "
    "what the question refers to. Do not answer the question. "
    'Return JSON {"queries": ["..."]} and nothing else.'
)


def wants_plan(definition: dict[str, object] | None) -> bool:
    """True unless the agent turns planning off. An agent with no library does not plan."""
    if not isinstance(definition, dict):
        return False
    knowledge = definition.get("knowledge")
    if not isinstance(knowledge, dict):
        return False
    collections = knowledge.get("collections")
    if not isinstance(collections, list) or not any(str(item).strip() for item in collections):
        return False
    raw = knowledge.get("plan_queries", knowledge.get("planQueries"))
    if raw is None:
        return True
    return raw is True


def planner_alias(store: Any, tenant_id: object, definition: dict[str, object] | None) -> str:
    """The quick alias when it is connected, otherwise the agent's own alias.

    ``knowledge.plannerAlias`` wins when it is set.
    """
    knowledge = definition.get("knowledge") if isinstance(definition, dict) else None
    model = definition.get("model") if isinstance(definition, dict) else None
    named = ""
    if isinstance(knowledge, dict):
        raw = knowledge.get("planner_alias", knowledge.get("plannerAlias"))
        if isinstance(raw, str) and raw.strip():
            named = raw.strip()
    fast = "fast"
    primary = "reasoning"
    if isinstance(model, dict):
        fast_raw = model.get("fast_alias", model.get("fastAlias"))
        alias_raw = model.get("alias")
        if isinstance(fast_raw, str) and fast_raw.strip():
            fast = fast_raw.strip()
        if isinstance(alias_raw, str) and alias_raw.strip():
            primary = alias_raw.strip()
    if named:
        return named
    if _connected(store, tenant_id, fast):
        return fast
    return primary


def _connected(store: Any, tenant_id: object, alias: str) -> bool:
    checker = getattr(store, "_completion_call", None)
    if not callable(checker) or not isinstance(tenant_id, uuid.UUID):
        return False
    try:
        return checker(tenant_id, alias) is not None
    except TypeError, ValueError:
        return False


async def plan_search_queries(
    store: Any,
    tenant_id: object,
    alias: str,
    question: str,
    earlier: list[str] | None = None,
) -> list[str] | None:
    """One to four queries, or None when planning did not produce any."""
    if not question.strip() or not isinstance(tenant_id, uuid.UUID):
        return None
    if not _connected(store, tenant_id, alias):
        return None
    complete = getattr(store, "complete_turn", None)
    if not callable(complete):
        return None
    context = "\n".join(text.strip() for text in earlier or [] if text.strip())
    evidence = wrap_untrusted(source="user_question", content=question.strip())
    if context:
        evidence = wrap_untrusted(source="earlier_turns", content=context) + "\n\n" + evidence
    messages = [
        {"role": "system", "content": _TASK},
        {"role": "user", "content": evidence},
    ]
    try:
        result = await complete(
            messages, [], tenant_id=tenant_id, model_alias=alias, max_tokens=300
        )
    except TypeError:
        try:
            result = await complete(messages, [], tenant_id=tenant_id, model_alias=alias)
        except TypeError, ValueError:
            return None
    except ValueError, OSError:
        return None
    text = ""
    if isinstance(result, dict):
        text = str(result.get("text") or "")
    elif isinstance(result, str):
        text = result
    return _queries(text, question)


def _queries(raw: str, question: str) -> list[str] | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = orjson.loads(raw[start : end + 1])
    except orjson.JSONDecodeError:
        return None
    rows = value.get("queries") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        return None
    found: list[str] = []
    seen: set[str] = set()
    for item in rows:
        text = " ".join(str(item).split())
        key = text.casefold()
        if not text or key in seen or len(text) > 300:
            continue
        seen.add(key)
        found.append(text)
        if len(found) >= _MAX_QUERIES:
            break
    if not found:
        return None
    if len(found) == 1 and found[0].casefold() == " ".join(question.split()).casefold():
        return None
    return found

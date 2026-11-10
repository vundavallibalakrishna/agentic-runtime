"""Scripted model for CI. It chooses a tool from the user text, then quotes the result.

The expectations in tasks.yaml are not read here. A change to a golden that the
scripted model cannot satisfy fails the dry-run scorecard.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_REQUIREMENT = re.compile(r'requirement:\s*"([^"]+)"')

Matcher = Callable[[str, str | None, str | None], dict[str, object] | None]


def quote_result(content: str) -> str:
    """Final answer for the dry-run model: the tool text, with an honest miss called out."""
    text = content.strip()
    if not text:
        return "The tool returned an empty result."
    lowered = text.lower()
    # The document banner says "not found" even on a hit. Only a verdict counts.
    missing = "not_found" in lowered or "no sufficiently relevant" in lowered
    if missing:
        return f"not_found. The passage was not found.\n{text[:1500]}"
    return text[:1500]


class DryRunCompleter:
    """Drop-in ``complete_turn``. The first turn calls a tool. The next turn quotes it."""

    async def __call__(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del tools, tenant_id, model_alias
        tool_text = _last_tool(messages)
        if tool_text is not None:
            return _turn(quote_result(tool_text), [])
        call = choose(_user_text(messages))
        if call is None:
            return _turn("I do not know which tool to use.", [])
        return _turn("", [call])


def choose(instruction: str) -> dict[str, object] | None:
    """Pick one tool call from the user instruction. None when nothing matches."""
    document_id = _document_id(instruction)
    requirement = _requirement(instruction)
    lowered = instruction.lower()
    for matcher in _MATCHERS:
        call = matcher(lowered, document_id, requirement)
        if call is not None:
            return call
    return None


def _requirement_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    if "requirement:" not in lowered or document_id is None or requirement is None:
        return None
    return _call(
        "documents__judge",
        {"documentId": document_id, "statements": [requirement]},
    )


def _summarise_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del requirement
    if "summarise" not in lowered and "summarize" not in lowered:
        return None
    if document_id is None:
        return None
    return _call("documents__summarise", {"documentId": document_id})


def _knowledge_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "visitor desk" not in lowered and "knowledge" not in lowered:
        return None
    return _call("knowledge__search", {"query": "visitor desk"})


def _query_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "warehouse" not in lowered and "public.orders" not in lowered:
        return None
    return _call(
        "data__query",
        {"connection": "Warehouse", "sql": "SELECT sku, quantity FROM public.orders"},
    )


def _chart_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "bar chart" not in lowered:
        return None
    return _call(
        "general__chart",
        {
            "kind": "bar",
            "xKey": "region",
            "yKey": "value",
            "rows": [
                {"region": "North", "value": 10},
                {"region": "South", "value": 4},
            ],
        },
    )


def _export_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "orders.csv" not in lowered and "export a csv" not in lowered:
        return None
    return _call(
        "general__export_table",
        {
            "path": "outputs/orders.csv",
            "format": "csv",
            "rows": [{"sku": "paper", "quantity": 4}],
        },
    )


def _http_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "post" not in lowered:
        return None
    return _call(
        "general__http",
        {
            "method": "POST",
            "url": "https://example.com/gym/orders",
            "json": {"sku": "paper"},
        },
    )


def _fetch_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "fetch" not in lowered:
        return None
    return _call("general__fetch", {"url": "https://example.com/gym"})


def _file_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "note.txt" not in lowered:
        return None
    return _call("general__read_file", {"path": "/workspace/inputs/note.txt"})


def _shell_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "shell" not in lowered:
        return None
    return _call("general__shell", {"command": "printf 'gym-shell\\n'"})


def _code_call(
    lowered: str, document_id: str | None, requirement: str | None
) -> dict[str, object] | None:
    del document_id, requirement
    if "python" not in lowered:
        return None
    return _call("general__code", {"source": "print(17 * 19)"})


_MATCHERS: tuple[Matcher, ...] = (
    _requirement_call,
    _summarise_call,
    _knowledge_call,
    _query_call,
    _chart_call,
    _export_call,
    _http_call,
    _fetch_call,
    _file_call,
    _shell_call,
    _code_call,
)


def _call(name: str, arguments: dict[str, object]) -> dict[str, object]:
    return {"id": "gym", "name": name, "arguments": arguments}


def _turn(text: str, calls: list[dict[str, object]]) -> dict[str, object]:
    return {
        "text": text,
        "tool_calls": calls,
        "usage": {"tokens_in": 1, "tokens_out": 1},
        "real": True,
    }


def _user_text(messages: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)


def _last_tool(messages: list[dict[str, object]]) -> str | None:
    found: str | None = None
    for message in messages:
        if message.get("role") != "tool":
            continue
        content = message.get("content")
        if isinstance(content, str):
            found = content
    return found


def _document_id(instruction: str) -> str | None:
    match = _UUID.search(instruction)
    return None if match is None else match.group(0)


def _requirement(instruction: str) -> str | None:
    match = _REQUIREMENT.search(instruction)
    return None if match is None else match.group(1)

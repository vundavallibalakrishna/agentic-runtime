"""Rolling summaries and tool-result folding. Spec: docs/03-specs/07-agent-runtime.md §5."""

import re
from typing import TYPE_CHECKING

import httpx

from ar_domain.memory.metrics import COMPACTIONS
from ar_domain.prompts.budget import estimate_tokens

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_CITE = re.compile(r"\[\d+\]")
_KEEP_MESSAGES = 12
_KEEP_TOOL_STEPS = 4


def count_tokens(text: str, *, tokenize_url: str = "") -> int:
    """Prefer ``/v1/tokenize``. Fall back to the local estimate."""
    if tokenize_url:
        remote = _remote_count(tokenize_url, text)
        if remote is not None:
            return remote
    return estimate_tokens(text)


def needs_compaction(
    text: str, *, context_window: int, threshold: float, tokenize_url: str = ""
) -> bool:
    """True when the next prompt would pass the fraction of the context window."""
    if context_window <= 0:
        return False
    return count_tokens(text, tokenize_url=tokenize_url) > threshold * context_window


def compact_context(
    messages: Sequence[Mapping[str, object]],
    *,
    context_window: int,
    threshold: float = 0.7,
    tokenize_url: str = "",
) -> dict[str, object]:
    """Fold old turns, stub old tool results, and fail closed when it still does not fit."""
    before = count_tokens(_join(messages), tokenize_url=tokenize_url)
    folded, kept = _split(messages)
    summary = summarise(folded)
    folded_tools = _fold_tools(kept)
    summary_through = str(folded[-1].get("id") or "") if folded else ""
    after_messages: list[Mapping[str, object]] = [
        {"role": "system", "content": summary},
        *folded_tools,
    ]
    after = count_tokens(_join(after_messages), tokenize_url=tokenize_url)
    if folded:
        COMPACTIONS.inc()
    failed = ""
    if context_window > 0 and after > context_window:
        failed = "context_length_exceeded"
    elif context_window > 0 and before <= threshold * context_window and not folded:
        failed = ""
    return {
        "summary": summary,
        "summary_through_message_id": summary_through,
        "messages": folded_tools,
        "tokens_before": before,
        "tokens_after": after,
        "folded": len(folded),
        "error": failed,
    }


def summarise(messages: Sequence[Mapping[str, object]]) -> str:
    """Keep decisions, file ids and citation markers from the folded turns."""
    if not messages:
        return ""
    ids: list[str] = []
    cites: list[str] = []
    notes: list[str] = []
    for message in messages:
        text = str(message.get("content") or "")
        ids.extend(_UUID.findall(text))
        cites.extend(_CITE.findall(text))
        if any(word in text.lower() for word in ("decide", "decision", "agreed", "file")):
            notes.append(text[:180])
    lines = ["Summary of the earlier conversation."]
    if notes:
        lines.append("Decisions and facts: " + " | ".join(notes[:8]))
    if ids:
        lines.append("File ids: " + ", ".join(dict.fromkeys(ids)))
    if cites:
        lines.append("Citations: " + ", ".join(dict.fromkeys(cites)))
    return "\n".join(lines)


def _split(
    messages: Sequence[Mapping[str, object]],
) -> tuple[list[Mapping[str, object]], list[Mapping[str, object]]]:
    if len(messages) <= _KEEP_MESSAGES:
        return [], list(messages)
    return list(messages[:-_KEEP_MESSAGES]), list(messages[-_KEEP_MESSAGES:])


def _fold_tools(messages: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    indexes = [index for index, message in enumerate(messages) if message.get("role") == "tool"]
    stale = set(indexes[:-_KEEP_TOOL_STEPS]) if len(indexes) > _KEEP_TOOL_STEPS else set()
    folded: list[dict[str, object]] = []
    for index, message in enumerate(messages):
        if index not in stale:
            folded.append(dict(message))
            continue
        text = str(message.get("content") or "")
        preview = text[:300]
        file_ids = _UUID.findall(text)
        file_note = f" file {file_ids[0]}" if file_ids else ""
        tool = str(message.get("tool") or "tool")
        stub = dict(message)
        stub["content"] = f"[earlier result of {tool}: {preview};{file_note}]"
        folded.append(stub)
    return folded


def _join(messages: Sequence[Mapping[str, object]]) -> str:
    return "\n".join(str(message.get("content") or "") for message in messages)


def _remote_count(url: str, text: str) -> int | None:
    try:
        response = httpx.post(
            url.rstrip("/") + "/v1/tokenize",
            json={"model": "fake-chat", "text": text},
            timeout=2.0,
        )
    except httpx.HTTPError:
        return None
    if response.status_code >= 300:
        return None
    body = response.json()
    count = body.get("count")
    if isinstance(count, int):
        return count
    return None

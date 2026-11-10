"""Token budget, rolling summary and retrievable tool output.

Full tool text is kept on the run checkpoint. The prompt sees a short copy
and an output id the ``context.retrieve`` tool can read back.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from ar_domain.memory.compaction import compact_context
from ar_domain.prompts.budget import estimate_tokens

if TYPE_CHECKING:
    from typing import Any

_TOOL_CAP = 1_500
_SUMMARY_PREFIX = "Earlier conversation, summarised:"


def fit_messages(
    messages: list[dict[str, object]],
    *,
    max_tokens: int,
    retained: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, int] | None]:
    """Shrink the prompt when it would pass 70% of the token budget.

    Returns the messages to send and a compaction note, or None when nothing moved.
    """
    if max_tokens <= 0:
        return messages, None
    truncated = _truncate_tools(messages, retained)
    window = max_tokens
    text = "\n".join(str(item.get("content") or "") for item in truncated)
    if estimate_tokens(text) <= int(window * 0.7):
        if truncated == messages:
            return messages, None
        return truncated, {
            "tokens_before": estimate_tokens(_join(messages)),
            "tokens_after": estimate_tokens(text),
        }
    folded = compact_context(truncated, context_window=window, threshold=0.7)
    summary = str(folded.get("summary") or "").strip()
    kept = folded.get("messages")
    next_messages: list[dict[str, object]] = []
    if summary:
        next_messages.append({"role": "system", "content": f"{_SUMMARY_PREFIX}\n{summary}"})
    if isinstance(kept, list):
        next_messages.extend(item for item in kept if isinstance(item, dict))
    if not next_messages:
        return truncated, None
    before = int(folded.get("tokens_before") or 0)
    after = int(folded.get("tokens_after") or 0)
    retained["rolling_summary"] = summary
    return next_messages, {"tokens_before": before, "tokens_after": after}


def retain_output(retained: dict[str, object], text: str) -> str:
    """Store the full tool text and return its id."""
    book = retained.get("outputs")
    if not isinstance(book, dict):
        book = {}
        retained["outputs"] = book
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    book[digest] = text
    return digest


def read_output(run: dict[str, object], output_id: str) -> str | None:
    """Full text for an id, from the checkpoint the loop wrote."""
    checkpoint = run.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return None
    retained = checkpoint.get("context")
    if not isinstance(retained, dict):
        return None
    outputs = retained.get("outputs")
    if not isinstance(outputs, dict):
        return None
    found = outputs.get(output_id)
    return found if isinstance(found, str) else None


def context_book(run: dict[str, object]) -> dict[str, object]:
    checkpoint = run.get("checkpoint")
    if not isinstance(checkpoint, dict):
        checkpoint = {}
        run["checkpoint"] = checkpoint
    retained = checkpoint.get("context")
    if not isinstance(retained, dict):
        retained = {}
        checkpoint["context"] = retained
    return retained


def _truncate_tools(
    messages: list[dict[str, object]], retained: dict[str, object]
) -> list[dict[str, object]]:
    changed = False
    next_messages: list[dict[str, object]] = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "tool" and isinstance(content, str) and len(content) > _TOOL_CAP:
            output_id = retain_output(retained, content)
            copy = dict(message)
            copy["content"] = (
                content[:_TOOL_CAP]
                + f"\n[truncated output_id={output_id}; call context.retrieve to read the rest]"
            )
            next_messages.append(copy)
            changed = True
        else:
            next_messages.append(message)
    return next_messages if changed else messages


def _join(messages: list[dict[str, object]]) -> str:
    return "\n".join(str(item.get("content") or "") for item in messages)


def public_route(row: dict[str, Any]) -> dict[str, str]:
    """Route fields safe to return. The secret value is not one of them."""
    return {
        "id": str(row.get("id") or ""),
        "baseUrl": str(row.get("base_url") or row.get("baseUrl") or ""),
        "model": str(row.get("model") or ""),
        "secretName": str(row.get("secret_name") or row.get("secretName") or ""),
    }

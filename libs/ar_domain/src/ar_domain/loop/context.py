"""Token budget, rolling summary and retrievable tool output.

Full tool text is kept on the run checkpoint. The prompt sees the first part
and an output id the ``context.retrieve`` tool reads on from, a part at a time.
The size of a part and the fill level that starts a summary are the agent's own
``context`` settings.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from ar_domain.memory.compaction import compact_context
from ar_domain.prompts.budget import estimate_tokens

if TYPE_CHECKING:
    from typing import Any

_CHARS_PER_TOKEN = 4
_SUMMARY_PREFIX = "Earlier conversation, summarised:"
RETRIEVE = "context.retrieve"


def context_limits(definition: dict[str, object]) -> dict[str, float]:
    """The agent's context settings, with the contract's defaults for anything omitted."""
    from ar_contracts.definitions import ContextSpec  # noqa: PLC0415

    raw = definition.get("context")
    source = raw if isinstance(raw, dict) else {}
    try:
        spec = ContextSpec.model_validate(source)
    except ValueError:
        spec = ContextSpec()
    return {
        "tool_result_max_tokens": spec.tool_result_max_tokens,
        "compaction_threshold": spec.compaction_threshold,
    }


def fit_messages(
    messages: list[dict[str, object]],
    *,
    max_tokens: int,
    retained: dict[str, object],
    tool_result_max_tokens: int,
    threshold: float,
) -> tuple[list[dict[str, object]], dict[str, int] | None]:
    """Shorten long tool results and summarise once the prompt passes the threshold.

    Returns the messages to send and a compaction note, or None when nothing moved.
    """
    if max_tokens <= 0:
        return messages, None
    part = max(1, tool_result_max_tokens) * _CHARS_PER_TOKEN
    retained["part_chars"] = part
    truncated = _truncate_tools(messages, retained, part)
    window = max_tokens
    text = "\n".join(str(item.get("content") or "") for item in truncated)
    if estimate_tokens(text) <= int(window * threshold):
        if truncated == messages:
            return messages, None
        return truncated, {
            "tokens_before": estimate_tokens(_join(messages)),
            "tokens_after": estimate_tokens(text),
        }
    folded = compact_context(truncated, context_window=window, threshold=threshold)
    summary = str(folded.get("summary") or "").strip()
    kept = folded.get("messages")
    next_messages: list[dict[str, object]] = []
    if summary:
        next_messages.append({"role": "system", "content": f"{_SUMMARY_PREFIX}\n{summary}"})
    if isinstance(kept, list):
        next_messages.extend(item for item in kept if isinstance(item, dict))
    if not next_messages:
        return truncated, None
    before = _whole(folded.get("tokens_before"))
    after = _whole(folded.get("tokens_after"))
    retained["rolling_summary"] = summary
    return next_messages, {"tokens_before": before, "tokens_after": after}


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return int(value)


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
    outputs = _retained(run).get("outputs")
    if not isinstance(outputs, dict):
        return None
    found = outputs.get(output_id)
    return found if isinstance(found, str) else None


def read_part(run: dict[str, object], output_id: str, offset: int) -> dict[str, object] | None:
    """One part of a stored output, sized so the prompt takes it whole."""
    full = read_output(run, output_id)
    if full is None:
        return None
    size = _retained(run).get("part_chars")
    room = size if isinstance(size, int) and not isinstance(size, bool) and size > 0 else len(full)
    start = min(max(0, offset), len(full))
    # The note that says where to read on must fit in the same part.
    end = min(len(full), start + max(1, room - _NOTE_ROOM))
    text = full[start:end]
    if end < len(full):
        text += shortened_note(output_id, start, end, len(full))
    return {"text": text, "next_offset": end if end < len(full) else None}


def has_shortened(run: dict[str, object]) -> bool:
    """True once any tool result on this run was shortened in the prompt."""
    return bool(_retained(run).get("outputs"))


def _retained(run: dict[str, object]) -> dict[str, object]:
    checkpoint = run.get("checkpoint")
    retained = checkpoint.get("context") if isinstance(checkpoint, dict) else None
    return retained if isinstance(retained, dict) else {}


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


_NOTE_ROOM = 200


def shortened_note(output_id: str, start: int, end: int, total: int) -> str:
    return (
        f"\n[shortened: characters {start} to {end} of {total} shown; call {RETRIEVE} with "
        f"output_id={output_id} and offset={end} to read on]"
    )


def _truncate_tools(
    messages: list[dict[str, object]], retained: dict[str, object], part: int
) -> list[dict[str, object]]:
    changed = False
    next_messages: list[dict[str, object]] = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "tool" and isinstance(content, str) and len(content) > part:
            output_id = retain_output(retained, content)
            copy = dict(message)
            shown = max(1, part - _NOTE_ROOM)
            copy["content"] = content[:shown] + shortened_note(output_id, 0, shown, len(content))
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

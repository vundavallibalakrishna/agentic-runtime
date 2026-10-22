"""Hook memory into an in-process run. Spec: docs/03-specs/07-agent-runtime.md §2."""

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_domain.agents.access import Actor
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.compaction import compact_context, needs_compaction
from ar_domain.prompts.assembler import build_prompt


def prepare_prompt(
    store: Any,
    run: dict[str, object],
    conversation: dict[str, object],
    definition: dict[str, object],
    text: str,
    *,
    names: list[str],
) -> str:
    """Recall memory, compact when needed, and return the prompt hash."""
    history = _history(store, conversation.get("id"), run.get("input_message_id"))
    window = _window(definition)
    threshold = _threshold(definition)
    joined = "\n".join(str(item.get("content") or "") for item in history) + "\n" + text
    if needs_compaction(joined, context_window=window, threshold=threshold):
        compacted = compact_context(history, context_window=window, threshold=threshold)
        if compacted.get("summary"):
            conversation["rolling_summary"] = compacted["summary"]
            conversation["summary_through_message_id"] = compacted["summary_through_message_id"]
        run["compaction"] = {
            "tokens_before": compacted["tokens_before"],
            "tokens_after": compacted["tokens_after"],
            "error": compacted["error"],
        }
        if compacted.get("error") == "context_length_exceeded":
            run["context_error"] = "context_length_exceeded"
    actor = _actor(run)
    block, facts = MemoryBook(store).prompt_block(
        actor,
        query=text,
        agent_id=_uuid(run.get("agent_id")),
        definition=definition,
    )
    run["memory"] = block
    run["recalled"] = [dict(item) for item in facts]
    bundle = build_prompt(
        {
            "definition": definition,
            "user_text": text,
            "files": names,
            "history": history,
            "memory": block,
            "summary": str(conversation.get("rolling_summary") or ""),
            "documents": run.get("documents"),
        }
    )
    run["prompt_messages"] = [dict(item) for item in bundle.messages]
    return bundle.prompt_hash


def remember_turn(
    store: Any, run: dict[str, object], user_text: str, answer: str
) -> list[dict[str, object]]:
    """Extract after a completed top-level turn. Tool text is not an argument."""
    return MemoryBook(store).extract_turn(run, user_text, answer)


def _history(store: Any, conversation_id: object, skip: object) -> list[dict[str, str]]:
    rows: list[dict[str, object]] = []
    messages = getattr(store, "messages", {})
    if not isinstance(messages, dict):
        return []
    for message in messages.values():
        if not isinstance(message, dict):
            continue
        if message.get("conversation_id") != conversation_id or message.get("id") == skip:
            continue
        if message.get("role") not in {"user", "assistant", "tool"}:
            continue
        if message.get("status") not in {None, "completed"}:
            continue
        rows.append(message)
    rows.sort(key=lambda item: str(item.get("created_at") or ""))
    return [
        {
            "id": str(message.get("id") or ""),
            "role": str(message.get("role") or "user"),
            "content": str(message.get("text") or ""),
        }
        for message in rows
    ]


def _actor(run: dict[str, object]) -> Actor:
    return Actor(
        tenant_id=_uuid(run.get("tenant_id")) or uuid.UUID(int=0),
        user_id=_uuid(run.get("user_id")) or uuid.UUID(int=0),
        permissions=frozenset({"chat:use"}),
    )


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    return None


def _window(definition: dict[str, object]) -> int:
    raw = definition.get("context_window")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return 8000


def _threshold(definition: dict[str, object]) -> float:
    context = definition.get("context")
    if isinstance(context, dict):
        raw = context.get("compaction_threshold", context.get("compactionThreshold", 0.7))
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
    return 0.7

"""Fold old turns into a rolling summary. Spec: docs/03-specs/07-agent-runtime.md §5."""

from temporalio import activity

from ar_domain.memory.compaction import compact_context as _compact
from ar_domain.prompts.assembler import build_prompt


@activity.defn(name="compact_context")
async def compact_context(payload: dict[str, object]) -> dict[str, object]:
    """Summarise old turns and return the prompt that would be sent next."""
    raw = payload.get("messages")
    messages = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    window = payload.get("context_window")
    size = window if isinstance(window, int) and not isinstance(window, bool) else 8000
    threshold = payload.get("threshold")
    fraction = float(threshold) if isinstance(threshold, (int, float)) else 0.7
    url = str(payload.get("tokenize_url") or "")
    result = _compact(messages, context_window=size, threshold=fraction, tokenize_url=url)
    bundle = build_prompt(
        {
            "definition": {"persona": {"display_name": "Assistant"}, "instructions": "Help."},
            "summary": result["summary"],
            "history": result["messages"],
            "user_text": str(payload.get("user_text") or ""),
        }
    )
    result["prompt_hash"] = bundle.prompt_hash
    result["prompt"] = [dict(item) for item in bundle.messages]
    return result

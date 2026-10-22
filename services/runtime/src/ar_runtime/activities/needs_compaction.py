"""Cheap token check before compaction. Spec: docs/03-specs/07-agent-runtime.md §5."""

from temporalio import activity

from ar_domain.memory.compaction import needs_compaction as _needs


@activity.defn(name="needs_compaction")
async def needs_compaction(payload: dict[str, object]) -> dict[str, bool]:
    """Return whether the next prompt crosses the compaction threshold."""
    window = payload.get("context_window")
    threshold = payload.get("threshold")
    size = window if isinstance(window, int) and not isinstance(window, bool) else 8000
    fraction = float(threshold) if isinstance(threshold, (int, float)) else 0.7
    text = str(payload.get("text") or "")
    url = str(payload.get("tokenize_url") or "")
    return {"compact": _needs(text, context_window=size, threshold=fraction, tokenize_url=url)}

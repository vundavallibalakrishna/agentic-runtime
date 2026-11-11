"""One identity for a logical tool call.

Chat, research, routines and subagents all build the key here. A retry of the
same call (same run, step, query and provider id or index) produces the same
key. A different query, step or call does not.
"""

from __future__ import annotations


def tool_call_idempotency_key(
    *,
    run_id: object,
    model_call_id: object = "",
    step: object | None = None,
    query_id: object | None = None,
    call_index: object | None = None,
    qualified_name: object | None = None,
) -> str:
    """Stable key for one logical tool call.

    The parts are the run, the model step, the research query or subtask, the
    tool, and either the provider tool-call id or the call index. Both the id
    and the index are included when both are known, so a repeated provider id
    in one step does not collide and a retry of that same call still matches.
    """
    parts = [str(run_id or "")]
    if step not in (None, ""):
        parts.append(f"s{step}")
    if query_id not in (None, ""):
        parts.append(f"q{query_id}")
    if qualified_name not in (None, ""):
        parts.append(str(qualified_name))
    ident = str(model_call_id or "").strip()
    if ident:
        parts.append(ident)
    elif call_index is not None:
        parts.append(f"i{call_index}")
    else:
        parts.append("call")
    if call_index is not None and ident:
        parts.append(f"i{call_index}")
    return ":".join(parts)

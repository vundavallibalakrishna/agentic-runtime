"""What /v1, MCP and A2A may show. Raw thinking stays off unless the caller asks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_HIDDEN = frozenset({"reasoning.delta"})

# A finished public turn. Reasoning, when shown, sits between the message start and its close.
# Tool calls open before they close. Exactly one terminal event ends the run.
_BEFORE = {
    "message.delta": "message.started",
    "message.completed": "message.started",
    "reasoning.delta": "message.started",
    "tool_call.completed": "tool_call.started",
    "tool_call.failed": "tool_call.started",
}
_TERMINAL = frozenset({"run.completed", "run.failed", "run.cancelled", "run.budget_exceeded"})


def include_reasoning(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def visible_event(event: dict[str, Any], *, show_reasoning: bool) -> bool:
    if show_reasoning:
        return True
    return str(event.get("type") or "") not in _HIDDEN


def public_events(events: list[dict[str, Any]], *, show_reasoning: bool) -> list[dict[str, Any]]:
    return [event for event in events if visible_event(event, show_reasoning=show_reasoning)]


def public_content(message: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Assistant content parts for a public reply. Thinking text is not a part."""
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    parts: list[dict[str, Any]] = []
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"reasoning", "thinking"}:
                continue
            parts.append(part)
    if parts:
        return parts
    text = str(message.get("text") or "")
    return [{"type": "text", "text": text}] if text else []


def event_order_ok(types: list[str]) -> bool:
    """True when a run's event types respect the stream ordering rules."""
    seen: set[str] = set()
    terminal = False
    for name in types:
        if terminal:
            return False
        required = _BEFORE.get(name)
        if required is not None and required not in seen:
            return False
        if name in _TERMINAL:
            terminal = True
        seen.add(name)
    return True

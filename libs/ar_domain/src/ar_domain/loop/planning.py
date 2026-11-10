"""Optional structured plan before the tool loop. Spec: stage 10.

The model is asked for a short JSON plan. The run stream carries ``plan.updated``.
A failed tool sets a replan when planning is enabled on the agent.
"""

from __future__ import annotations

import orjson

PLAN_INSTRUCTION = (
    "Write a short plan for the user's request. Reply with only a JSON object "
    '{"steps":[{"id":"1","title":"what you will do"}]}. Use at most six steps. '
    "Do not call tools in this reply."
)


def planning_enabled(definition: dict[str, object] | None) -> bool:
    """True when this agent definition opts into a plan step."""
    if not isinstance(definition, dict):
        return False
    raw = definition.get("planning")
    if not isinstance(raw, dict):
        return False
    return raw.get("enabled") is True


def parse_plan(text: str) -> tuple[list[dict[str, str]] | None, str]:
    """Return plan steps, or an error string when the text is not the JSON plan."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError as exc:
        return None, f"plan was not JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "plan was not a JSON object"
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        return None, "plan.steps must be a non-empty list"
    items: list[dict[str, str]] = []
    for index, step in enumerate(steps[:6]):
        if not isinstance(step, dict):
            return None, "each plan step must be an object"
        title = str(step.get("title") or "").strip()
        if not title:
            return None, "each plan step needs a title"
        item_id = str(step.get("id") or index + 1)
        items.append({"id": item_id, "title": title[:160], "status": "pending"})
    if items:
        items[0]["status"] = "in_progress"
    return items, ""


def replan_instruction(reason: str) -> str:
    """Ask for a revised plan after a failed step."""
    detail = reason.strip() or "a step failed"
    return (
        "The previous plan failed: "
        f"{detail}. Reply with only a revised JSON plan "
        '{"steps":[{"id":"1","title":"..."}]}.'
    )

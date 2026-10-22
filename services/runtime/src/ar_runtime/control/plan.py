"""Apply a plan update. Spec: docs/03-specs/07-agent-runtime.md §6."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def apply_plan_update(store: Any, conversation_id: object, plan: list[object]) -> dict[str, object]:
    """Replace the conversation plan and describe the event the UI renders."""
    conversation = store.conversations.get(conversation_id)
    if isinstance(conversation, dict):
        conversation["plan"] = plan
    return {"type": "plan.updated", "plan": plan}

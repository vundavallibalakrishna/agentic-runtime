"""Start extraction when a top-level run completes. Spec: docs/03-specs/11-memory.md §4."""

from typing import TYPE_CHECKING

from ar_system.workflows.memory_extraction import drive_extraction

if TYPE_CHECKING:
    from typing import Any

    from ar_system.workflows.outbox_relay import RelayEvent

_STORE: Any = None


def bind_store(store: Any) -> None:
    """The dev worker points this at the process store."""
    global _STORE  # noqa: PLW0603
    _STORE = store


async def on_run_completed(event: RelayEvent) -> None:
    """Load the turn from the store. The outbox payload has ids, not content."""
    store = _STORE
    if store is None:
        return
    run = _run(store, event.payload.get("run_id") or event.payload.get("runId"))
    if run is None:
        return
    user_text, assistant_text = _turn(store, run)
    drive_extraction(
        {
            "user_text": user_text,
            "assistant_text": assistant_text,
            "tool_text": "",
            "run": run,
        },
        store,
    )


def _run(store: Any, run_id: object) -> dict[str, object] | None:
    runs = getattr(store, "runs", {})
    if not isinstance(runs, dict):
        return None
    for key, value in runs.items():
        if not isinstance(value, dict):
            continue
        if str(key) == str(run_id) or str(value.get("id")) == str(run_id):
            return value
    return None


def _turn(store: Any, run: dict[str, object]) -> tuple[str, str]:
    messages = getattr(store, "messages", {})
    if not isinstance(messages, dict):
        return "", ""
    user = messages.get(run.get("input_message_id"))
    assistant = messages.get(run.get("assistant_message_id"))
    user_text = str(user.get("text") or "") if isinstance(user, dict) else ""
    assistant_text = str(assistant.get("text") or "") if isinstance(assistant, dict) else ""
    return user_text, assistant_text

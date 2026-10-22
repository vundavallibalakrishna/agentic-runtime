"""Memory extraction. Spec: docs/03-specs/11-memory.md §4.

The dev API extracts in process. This driver is what the system worker runs.
"""

from typing import TYPE_CHECKING

from temporalio import workflow

from ar_domain.memory.book import MemoryBook
from ar_domain.memory.extract import extraction_input, heuristic_ops, parse_ops

if TYPE_CHECKING:
    from typing import Any

_STORE: Any = None


def bind_store(store: Any) -> None:
    """Install the process store the subscriber and the tests share."""
    global _STORE  # noqa: PLW0603
    _STORE = store


def workflow_id(run_id: str) -> str:
    """Temporal workflow id ``memx-{run_id}``."""
    return f"memx-{run_id}"


def drive_extraction(payload: dict[str, object], store: Any | None = None) -> dict[str, object]:
    """Apply scripted or heuristic ops. Tool text is recorded as ignored."""
    user_text = str(payload.get("user_text") or "")
    assistant_text = str(payload.get("assistant_text") or "")
    tool_text = str(payload.get("tool_text") or "")
    model_output = str(payload.get("model_output") or "")
    visible = extraction_input(user_text, assistant_text)
    ops = parse_ops(model_output) or heuristic_ops(user_text)
    target = store if store is not None else _STORE
    facts: list[dict[str, object]] = []
    run = payload.get("run")
    if target is not None and isinstance(run, dict):
        facts = MemoryBook(target).extract_turn(
            run,
            user_text,
            assistant_text,
            model_output=model_output,
            tool_text=tool_text,
        )
    return {
        "input": visible,
        "ignored_tool_text": tool_text not in visible,
        "ops": ops,
        "facts": facts,
    }


@workflow.defn
class MemoryExtractionWorkflow:
    """Temporal shell. The payload carries the turn, not tool output."""

    @workflow.run
    async def run(self, payload: dict[str, object]) -> dict[str, object]:
        return drive_extraction(payload, _STORE)

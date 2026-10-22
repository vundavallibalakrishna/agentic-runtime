"""Gateway execution entry. Decisions stay in the shared tool pipeline."""

from typing import TYPE_CHECKING

from ar_domain.tools.pipeline import ToolPipeline

if TYPE_CHECKING:
    from typing import Any


def execute(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Run one tool call with the live policy decider."""
    return ToolPipeline(store).execute(request)

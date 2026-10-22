"""Gateway execution entry. Decisions stay in the shared tool pipeline."""

from typing import TYPE_CHECKING

from ar_domain.tools.pipeline import ToolPipeline

if TYPE_CHECKING:
    from typing import Any


def execute(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Run one tool call with the live policy decider."""
    from ar_mcp_gateway.builtins.files import forward as forward_files  # noqa: PLC0415
    from ar_mcp_gateway.builtins.sandbox import forward as forward_sandbox  # noqa: PLC0415

    result = ToolPipeline(store).execute(request)
    qualified = str(request.get("qualified_name") or "")
    if qualified.startswith("sandbox."):
        result["forwarded"] = forward_sandbox.__name__
    elif qualified.startswith("files."):
        result["forwarded"] = forward_files.__name__
    return result

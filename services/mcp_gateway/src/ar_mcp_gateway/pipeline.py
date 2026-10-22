"""Gateway execution entry. Decisions stay in the shared tool pipeline."""

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import QuotaExceededError
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.usage.service import UsageBook

if TYPE_CHECKING:
    from typing import Any


def execute(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Run one tool call with the live policy decider."""
    blocked = _quota(store, request)
    if blocked is not None:
        return blocked
    from ar_mcp_gateway.builtins.files import forward as forward_files  # noqa: PLC0415
    from ar_mcp_gateway.builtins.knowledge import forward as forward_knowledge  # noqa: PLC0415
    from ar_mcp_gateway.builtins.memory import forward as forward_memory  # noqa: PLC0415
    from ar_mcp_gateway.builtins.sandbox import forward as forward_sandbox  # noqa: PLC0415
    from ar_mcp_gateway.builtins.skills import forward as forward_skills  # noqa: PLC0415

    result = ToolPipeline(store).execute(request)
    qualified = str(request.get("qualified_name") or "")
    if qualified.startswith("sandbox."):
        result["forwarded"] = forward_sandbox.__name__
    elif qualified.startswith("files."):
        result["forwarded"] = forward_files.__name__
    elif qualified.startswith("knowledge."):
        result["forwarded"] = forward_knowledge.__name__
    elif qualified.startswith("memory."):
        result["forwarded"] = forward_memory.__name__
    elif qualified.startswith("skills."):
        result["forwarded"] = forward_skills.__name__
    return result


def _quota(store: Any, request: dict[str, object]) -> dict[str, object] | None:
    tenant = request.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        return None
    try:
        UsageBook(store).assert_tool(tenant, request.get("user_id"), request.get("agent_id"))
    except QuotaExceededError as exc:
        return {
            "status": "failed",
            "is_error": True,
            "text": str(exc),
            "error": {"code": "quota_exceeded", "message": str(exc)},
        }
    return None

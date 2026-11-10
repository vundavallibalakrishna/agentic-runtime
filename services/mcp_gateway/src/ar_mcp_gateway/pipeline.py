"""Gateway execution entry. Decisions stay in the shared tool pipeline.

Every call is audited here. Remote hosts are checked against the tenant allowlist
before the pipeline opens a connection. The tool's ``timeout_s`` is the deadline
the pipeline already enforces; this entry records it.
"""

import uuid
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ar_common.errors import QuotaExceededError
from ar_domain.audit.memory import remember
from ar_domain.tools.general import host_refusal
from ar_domain.tools.logic import as_int
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.usage.service import UsageBook

if TYPE_CHECKING:
    from typing import Any


def execute(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Run one tool call. Policy, egress, timeout and audit happen on this path."""
    blocked = _quota(store, request)
    if blocked is not None:
        _audit(store, request, blocked, timeout_s=None)
        return blocked
    refused = _egress(store, request)
    if refused is not None:
        _audit(store, request, refused, timeout_s=_timeout_s(store, request))
        return refused
    from ar_mcp_gateway.evals import prepare  # noqa: PLC0415

    mocked = prepare(store, request)
    if mocked is not None:
        _audit(store, request, mocked, timeout_s=_timeout_s(store, request))
        return mocked
    from ar_mcp_gateway.builtins.files import forward as forward_files  # noqa: PLC0415
    from ar_mcp_gateway.builtins.knowledge import forward as forward_knowledge  # noqa: PLC0415
    from ar_mcp_gateway.builtins.memory import forward as forward_memory  # noqa: PLC0415
    from ar_mcp_gateway.builtins.sandbox import forward as forward_sandbox  # noqa: PLC0415
    from ar_mcp_gateway.builtins.skills import forward as forward_skills  # noqa: PLC0415

    timeout_s = _timeout_s(store, request)
    result = ToolPipeline(store).execute(request)
    _audit(store, request, result, timeout_s=timeout_s)
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


def _timeout_s(store: Any, request: dict[str, object]) -> int:
    versions = getattr(store, "tool_versions", {})
    version = versions.get(request.get("tool_version_id")) if isinstance(versions, dict) else None
    if not isinstance(version, dict):
        return 30
    return as_int(version.get("timeout_s"), 30)


def _egress(store: Any, request: dict[str, object]) -> dict[str, object] | None:
    """Refuse a remote tool whose host is not on this tenant's allowlist."""
    versions = getattr(store, "tool_versions", {})
    servers = getattr(store, "tool_server_versions", {})
    version = versions.get(request.get("tool_version_id")) if isinstance(versions, dict) else None
    if not isinstance(version, dict):
        return None
    server_version = (
        servers.get(version.get("tool_server_version_id")) if isinstance(servers, dict) else None
    )
    endpoint = (
        str(server_version.get("endpoint_url") or "") if isinstance(server_version, dict) else ""
    )
    if not endpoint.startswith(("http://", "https://")):
        return None
    host = urlparse(endpoint).hostname or ""
    if not host:
        return _denied("the tool endpoint has no host")
    reason = host_refusal(
        store,
        {"_tenant_id": request.get("tenant_id")},
        str(version.get("name") or "tool"),
        host,
    )
    if reason is None:
        return None
    return _denied(reason)


def _denied(message: str) -> dict[str, object]:
    return {
        "status": "failed",
        "is_error": True,
        "result_preview": message,
        "error": {"code": "egress_denied", "message": message},
        "policy": {"decision": "deny", "message": message},
    }


def _audit(
    store: Any, request: dict[str, object], result: dict[str, object], *, timeout_s: int | None
) -> None:
    """One gateway audit row per call. The hash chain is Stage 8; this is the process log."""
    status = str(result.get("status") or "failed")
    error = result.get("error")
    code = error.get("code") if isinstance(error, dict) else ""
    denied = status == "denied" or code in {"policy_denied", "egress_denied"}
    remember(
        store,
        tenant_id=request.get("tenant_id"),
        actor_id=request.get("user_id"),
        action="tool.denied" if denied else "tool.called",
        target_type="tool_call",
        target_id=str(result.get("tool_call_id") or request.get("model_call_id") or ""),
        detail={
            "via": "gateway",
            "status": status,
            "timeout_s": timeout_s,
            "qualified_name": str(
                result.get("qualified_name") or request.get("qualified_name") or ""
            ),
        },
        outcome="failure" if status not in {"succeeded", "awaiting_approval"} else "success",
    )

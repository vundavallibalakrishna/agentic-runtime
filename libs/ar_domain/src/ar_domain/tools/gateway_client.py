"""Call the tool gateway over HTTP. The gateway is the only tool caller in production.

Dev and CI keep an in-process double so unit tests do not open a socket. A store
with ``tool_gateway_http`` set, and any production environment, posts to
``AR_MCP_GATEWAY_URL``. An empty URL is a refusal (``gateway_unavailable``),
not a local tool run.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

import httpx

from ar_common.internal_http import internal_post
from ar_common.logging import get_logger
from ar_common.offload import blocking

if TYPE_CHECKING:
    from typing import Any

_PRODUCTION = frozenset({"prod", "staging"})


def configure_gateway(store: Any, *, env: str = "") -> None:
    """Turn HTTP on for production, and whenever the gateway URL is set."""
    name = (env or os.environ.get("AR_ENV", "dev")).strip().lower()
    url = os.environ.get("AR_MCP_GATEWAY_URL", "").strip()
    if name in _PRODUCTION or url:
        store.tool_gateway_http = True


def http_gateway(store: Any) -> bool:
    """True when this process must not run tools itself."""
    return bool(getattr(store, "tool_gateway_http", False))


def execute_tool(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Run one tool call. Production posts to the gateway; tests stay in process."""
    if not http_gateway(store):
        from ar_domain.tools.pipeline import ToolPipeline  # noqa: PLC0415

        return ToolPipeline(store).execute(request)
    return _post(store, request)


def run_console_test(store: Any, request: dict[str, object]) -> dict[str, object]:
    """Run a console test of one tool. It goes where every tool call goes."""
    if not http_gateway(store):
        from ar_domain.tools.console import open_console_run  # noqa: PLC0415
        from ar_domain.tools.pipeline import ToolPipeline  # noqa: PLC0415

        return ToolPipeline(store).execute(open_console_run(store, request))
    body = _body(request)
    conversation_id = request.get("conversation_id")
    if isinstance(conversation_id, uuid.UUID):
        body["conversation_id"] = str(conversation_id)
    permissions = request.get("permissions")
    if isinstance(permissions, list):
        body["permissions"] = [str(item) for item in permissions]
    return _post(store, request, route="tool-calls:test", body=body)


def _post(
    store: Any,
    request: dict[str, object],
    *,
    route: str = "tool-calls:execute",
    body: dict[str, object] | None = None,
) -> dict[str, object]:
    url = os.environ.get("AR_MCP_GATEWAY_URL", "").strip().rstrip("/")
    if not url:
        return _unavailable("the tool gateway URL is not set")
    timeout = _timeout(store, request)
    body = _body(request) if body is None else body
    try:
        response = _send(f"{url}/internal/v1/{route}", body, timeout)
    except httpx.TimeoutException:
        return _unavailable(
            "The tool call timed out before the gateway finished. "
            "Whether it changed anything is not known."
        )
    except httpx.HTTPError as exc:
        reason = str(getattr(exc, "reason", "") or exc).strip()
        get_logger(__name__).warning(
            "tool_gateway_call_failed",
            error_type=type(exc).__name__,
            cause=reason[:300],
        )
        detail = f": {reason[:300]}" if reason else ""
        return _unavailable(f"the tool gateway did not answer{detail}")
    try:
        if response.status_code >= 400:
            return _unavailable(f"the tool gateway returned {response.status_code}")
        payload = response.json()
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    return (
        payload if isinstance(payload, dict) else _unavailable("the tool gateway returned nothing")
    )


def _send(url: str, body: dict[str, object], timeout: float) -> httpx.Response:
    """Post on the shared internal client: cluster egress and the install HMAC."""
    return blocking(lambda: internal_post(url, json=body, timeout=timeout))


def _timeout(store: Any, request: dict[str, object]) -> float:
    from ar_domain.tools.pipeline import caller_wait_s  # noqa: PLC0415

    versions = getattr(store, "tool_versions", {})
    version = versions.get(request.get("tool_version_id")) if isinstance(versions, dict) else None
    return caller_wait_s(version if isinstance(version, dict) else None)


def _body(request: dict[str, object]) -> dict[str, object]:
    """The execute route accepts snake_case. Ids travel as text."""
    keys = (
        "tenant_id",
        "user_id",
        "run_id",
        "agent_version_id",
        "tool_version_id",
        "arguments",
        "model_call_id",
        "dry_run",
        "synthetic",
        "approval_id",
        "args_hash",
        "agent_id",
        "step",
        "query_id",
        "call_index",
        "tool_call_id",
    )
    body: dict[str, object] = {}
    for key in keys:
        if key not in request:
            continue
        value = request[key]
        if isinstance(value, uuid.UUID):
            body[key] = str(value)
        elif key == "arguments" and isinstance(value, dict):
            body[key] = value
        elif key in {"dry_run", "synthetic"}:
            body[key] = bool(value)
        elif value is not None:
            body[key] = value
    body.setdefault("arguments", {})
    body.setdefault("model_call_id", "call")
    return body


def _unavailable(message: str) -> dict[str, object]:
    return {
        "status": "failed",
        "is_error": True,
        "result_preview": message,
        "error": {"code": "gateway_unavailable", "message": message},
    }

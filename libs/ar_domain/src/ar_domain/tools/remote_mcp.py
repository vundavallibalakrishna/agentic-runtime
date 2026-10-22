"""JSON-RPC client for a remote MCP server. Spec: docs/05-contracts/mcp-integration.md."""

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from ar_common.errors import ArError
from ar_common.http import assert_public_url

if TYPE_CHECKING:
    from typing import Any


class RemoteError(Exception):
    """The remote server did not return a tool result."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def auth_headers(mode: str, token: str) -> dict[str, str]:
    """Headers for one auth mode. The token never goes into a log line here."""
    if not token or mode == "none":
        return {}
    if mode == "static_secret":
        return {"x-api-key": token}
    return {"authorization": f"Bearer {token}"}


def list_remote(
    store: Any, url: str, token: str = "", mode: str = "none"
) -> list[dict[str, object]]:
    """Discover tools. A transport error becomes ``RemoteError``."""
    payload = _post(
        store, url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, token, mode
    )
    result = payload.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise RemoteError("tools/list returned no tools")
    found: list[dict[str, object]] = []
    for item in tools:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        found.append(
            {
                "name": str(item["name"]),
                "title": item.get("title") or item["name"],
                "description": item.get("description") or item["name"],
                "input_schema": item.get("inputSchema") or {"type": "object"},
                "risk_class": "R1",
                "annotations": item.get("annotations") or {},
            }
        )
    return found


def call_remote(  # noqa: PLR0917
    store: Any,
    url: str,
    name: str,
    arguments: dict[str, object],
    token: str,
    mode: str,
) -> dict[str, object]:
    """Call one tool. The result is untrusted text for the wrapper."""
    payload = _post(
        store,
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        token,
        mode,
    )
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "upstream error")
        return {"text": message, "structured": {}, "is_error": True, "code": "upstream_error"}
    result = payload.get("result")
    text = ""
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = str(content[0].get("text") or "")
        elif "text" in result:
            text = str(result.get("text") or "")
        if result.get("isError") is True:
            return {
                "text": text or "upstream error",
                "structured": {},
                "is_error": True,
                "code": "upstream_error",
            }
    return {
        "text": text,
        "structured": result if isinstance(result, dict) else {},
        "is_error": False,
    }


def _post(
    store: Any, url: str, body: dict[str, object], token: str, mode: str
) -> dict[str, object]:
    _guard(store, url)
    transport = getattr(store, "mcp_transport", None)
    try:
        with httpx.Client(transport=transport, timeout=5.0) as client:
            response = client.post(url, json=body, headers=auth_headers(mode, token))
            response.raise_for_status()
            loaded = response.json()
    except httpx.HTTPError as exc:
        raise RemoteError("the remote server did not answer") from exc
    if not isinstance(loaded, dict):
        raise RemoteError("the remote server returned an unexpected body")
    return loaded


def _guard(store: Any, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise RemoteError("a remote server needs an http(s) URL")
    resolver = getattr(store, "mcp_resolver", None)
    allow = getattr(store, "mcp_allow_hosts", ())
    hosts = allow if isinstance(allow, tuple | list) else ()
    try:
        if callable(resolver):
            assert_public_url(url, resolver=resolver, allow_hosts=hosts)
        else:
            assert_public_url(url, allow_hosts=hosts)
    except ArError as exc:
        raise RemoteError(str(exc)) from exc

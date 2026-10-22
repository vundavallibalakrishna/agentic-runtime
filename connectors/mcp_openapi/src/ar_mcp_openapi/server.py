"""Call an upstream HTTP API described by OpenAPI."""

from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx

from ar_common.http import Resolver, assert_public_url
from ar_mcp_openapi.parse import operations_from

if TYPE_CHECKING:
    from typing import Any


def handle(
    body: dict[str, Any],
    *,
    document: dict[str, object],
    base_url: str,
    transport: httpx.BaseTransport | None = None,
    token: str = "",
    resolver: Resolver | None = None,
) -> dict[str, object]:
    """JSON-RPC entry. Upstream calls go through the supplied base URL."""
    method = str(body.get("method") or "")
    request_id = body.get("id", 1)
    tools = operations_from(document)
    if method == "tools/list":
        listed = [
            {
                "name": item["name"],
                "description": item["description"],
                "inputSchema": item["input_schema"],
            }
            for item in tools
        ]
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": listed}}
    if method != "tools/call":
        return {"jsonrpc": "2.0", "id": request_id, "error": {"message": "unknown method"}}
    raw_params = body.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    name = str(params.get("name") or "")
    raw_arguments = params.get("arguments")
    arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
    match = next((item for item in tools if item["name"] == name), None)
    if match is None:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"message": "unknown tool"}}
    text, is_error = _call(
        match, arguments, base_url=base_url, transport=transport, token=token, resolver=resolver
    )
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": text}], "isError": is_error},
    }


def _call(
    tool: dict[str, object],
    arguments: dict[str, object],
    *,
    base_url: str,
    transport: httpx.BaseTransport | None,
    token: str,
    resolver: Resolver | None,
) -> tuple[str, bool]:
    path = str(tool["path"])
    for key, value in arguments.items():
        if key == "body":
            continue
        path = path.replace("{" + key + "}", str(value))
    url = urljoin(base_url if base_url.endswith("/") else base_url + "/", path.lstrip("/"))
    if resolver is None:
        assert_public_url(url)
    else:
        assert_public_url(url, resolver=resolver)
    headers = {"authorization": f"Bearer {token}"} if token else {}
    payload = arguments.get("body")
    try:
        with httpx.Client(transport=transport, timeout=5.0) as client:
            response = client.request(str(tool["method"]), url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        return str(exc), True
    if response.status_code >= 400:
        return response.text or "upstream error", True
    return response.text or "ok", False

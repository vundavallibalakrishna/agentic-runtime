"""MCP client depth: all content blocks and tools/list pagination. Task: M39-T06."""

from __future__ import annotations

from typing import Any

import httpx
import orjson

from ar_domain.tools.remote_mcp import _result_text, list_remote
from ar_testing.demo import demo_store

URL = "https://mcp.example/rpc"


def test_result_keeps_every_content_block() -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [
                {"type": "text", "text": "first"},
                {"type": "image", "mimeType": "image/png", "data": "QUJD"},
                {"type": "text", "text": "second"},
                {"type": "resource", "resource": {"uri": "file://r", "text": "a resource"}},
            ]
        },
    }
    outcome = _result_text(payload)
    assert outcome["is_error"] is False
    # Both text blocks are kept, not just the first, and the others are named.
    assert "first" in outcome["text"]
    assert "second" in outcome["text"]
    assert "[image: image/png]" in outcome["text"]
    assert "a resource" in outcome["text"]
    # The whole result survives in structured, so nothing is dropped.
    assert len(outcome["structured"]["content"]) == 4  # type: ignore[index]


def test_result_reports_an_error_flag() -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {"isError": True, "content": [{"type": "text", "text": "boom"}]},
    }
    outcome = _result_text(payload)
    assert outcome["is_error"] is True
    assert outcome["code"] == "upstream_error"
    assert "boom" in outcome["text"]


def _paging_store() -> tuple[Any, list[str | None]]:
    store = demo_store()
    store.mcp_resolver = lambda _host: ["93.184.216.34"]  # a public address, so _guard passes
    seen_sessions: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = orjson.loads(request.content or b"{}")
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}},
                headers={"mcp-session-id": "S1"},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/list":
            seen_sessions.append(request.headers.get("mcp-session-id"))
            cursor = (body.get("params") or {}).get("cursor")
            if not cursor:
                return httpx.Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "result": {
                            "tools": [
                                {"name": "alpha", "description": "a"},
                                {"name": "beta", "description": "b"},
                            ],
                            "nextCursor": "page-2",
                        },
                    },
                )
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {"tools": [{"name": "gamma", "description": "g"}]},
                },
            )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {}})

    store.mcp_transport = httpx.MockTransport(handler)
    return store, seen_sessions


def test_tools_list_follows_pages_in_one_session() -> None:
    store, seen_sessions = _paging_store()
    tools = list_remote(store, URL, transport="streamable")
    names = {str(tool["name"]) for tool in tools}
    assert names == {"alpha", "beta", "gamma"}
    # The first page opens the session; the second reuses its id rather than re-initialising.
    assert seen_sessions[0] is None or seen_sessions[0] == "S1"
    assert seen_sessions[-1] == "S1"

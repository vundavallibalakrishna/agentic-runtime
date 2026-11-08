"""One MCP session is reused across a run's tool calls. Task: M39-T06a."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import orjson

from ar_domain.tools.remote_mcp import call_remote
from ar_testing.demo import demo_store

URL = "https://mcp.example/rpc"


def _store() -> tuple[Any, list[str]]:
    store = demo_store()
    store.mcp_resolver = lambda _host: ["93.184.216.34"]
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = orjson.loads(request.content or b"{}")
        method = str(body.get("method") or "")
        methods.append(method)
        if method == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {}}},
                headers={"mcp-session-id": "S1"},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "ok"}]},
            },
        )

    store.mcp_transport = httpx.MockTransport(handler)
    return store, methods


def _call(store: Any, run_id: object) -> dict[str, object]:
    return call_remote(store, URL, "do", {}, "", "none", run_id=run_id)


def test_one_session_is_reused_across_a_runs_calls() -> None:
    store, methods = _store()
    run_id = uuid.uuid4()
    assert _call(store, run_id)["is_error"] is False
    assert _call(store, run_id)["is_error"] is False
    # The server is initialised once; the second tool call reuses the session.
    assert methods.count("initialize") == 1
    assert methods.count("tools/call") == 2


def test_without_a_run_each_call_initialises() -> None:
    store, methods = _store()
    _call(store, None)
    _call(store, None)
    assert methods.count("initialize") == 2


def test_different_runs_do_not_share_a_session() -> None:
    store, methods = _store()
    _call(store, uuid.uuid4())
    _call(store, uuid.uuid4())
    assert methods.count("initialize") == 2

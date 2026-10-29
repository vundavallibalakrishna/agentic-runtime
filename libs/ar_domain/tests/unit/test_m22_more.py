"""Extra paths for connections, MCP transports and HTTP import."""

# ruff: noqa: S105

import sys
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from ar_common.errors import ArError, ConflictError, ValidationFailedError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.describe import compile_description
from ar_domain.tools.http_tools import execute_operation, fetch_document, guard_public
from ar_domain.tools.imports import ToolImporter
from ar_domain.tools.registry import ToolRegistry
from ar_domain.tools.remote_mcp import (
    RemoteError,
    _frames,
    _json_from_sse,
    call_stdio,
    list_remote,
    list_stdio,
    safe_command,
)
from ar_domain.tools.service_connections import ConnectionBook, headers_for


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)


def test_connection_kinds_oauth_and_test() -> None:
    store = ChatService()
    book = ConnectionBook(store)
    actor = _actor()
    with pytest.raises(ValidationFailedError):
        book.create(actor, {"name": "1bad", "kind": "bearer", "secret": "x"})
    with pytest.raises(ValidationFailedError):
        book.create(actor, {"name": "ok", "kind": "nope", "secret": "x"})
    with pytest.raises(ValidationFailedError):
        book.create(actor, {"name": "basicone", "kind": "basic", "secret": "pw"})
    basic = book.create(
        actor,
        {
            "name": "basicone",
            "kind": "basic",
            "secret": "pw",
            "username": "ada",
            "probe_url": "https://example.com/health",
        },
    )
    with pytest.raises(ConflictError):
        book.create(actor, {"name": "basicone", "kind": "bearer", "secret": "x"})
    updated = book.update(
        actor,
        uuid.UUID(str(basic["id"])),
        {"header_name": "X-Token", "scopes": ["read"], "expires_at": ""},
    )
    assert updated["header_name"] == "X-Token"

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url
        headers = kwargs.get("headers")
        assert isinstance(headers, dict)
        assert str(headers["Authorization"]).startswith("Basic ")
        return httpx.Response(200, text="ok")

    store.http_send = send
    tested = book.test(actor, uuid.UUID(str(basic["id"])))
    assert tested["ok"] is True
    assert "password" not in str(tested)
    missing = book.test(actor, uuid.UUID(str(basic["id"])), url="")
    assert missing["ok"] is True or "test URL" in str(
        book.test(actor, uuid.UUID(str(basic["id"])), "")
    )
    book.revoke(actor, uuid.UUID(str(basic["id"])))
    with pytest.raises(ArError):
        headers_for(store, actor.tenant_id, actor.user_id, "basicone")

    client = book.create(
        actor,
        {
            "name": "machine",
            "kind": "oauth_client_credentials",
            "secret": "client-secret",
            "token_url": "memory://tokens",
            "client_id": "ar",
        },
    )
    minted = book.test(actor, uuid.UUID(str(client["id"])))
    assert minted["ok"] is True
    headers, _secret = headers_for(store, actor.tenant_id, actor.user_id, "machine")
    assert headers["Authorization"].startswith("Bearer ")

    oauth = book.create(
        actor,
        {
            "name": "userlogin",
            "kind": "oauth_authorization_code",
            "secret": "client-secret",
            "token_url": "memory://tokens",
            "authorize_url": "https://example.com/authorize",
            "client_id": "ar",
            "scopes": ["read"],
        },
    )
    started = book.start(actor, uuid.UUID(str(oauth["id"])))
    assert "code_challenge" in str(started["authorize_url"])

    async def _callback() -> dict[str, object]:
        return await book.callback("good-code", str(started["state"]))

    import asyncio

    granted = asyncio.run(_callback())
    assert granted["status"] == "active"
    with pytest.raises(ArError):
        asyncio.run(book.callback("good-code", "missing-state"))
    key = book.create(
        actor, {"name": "apikey", "kind": "api_key", "secret": "k" * 8, "header_name": "X-Key"}
    )
    assert key["has_secret"] is True
    bare = book.test(actor, uuid.UUID(str(key["id"])))
    assert bare["ok"] is False


def test_expired_connection_and_bad_token_host() -> None:
    store = ChatService()
    book = ConnectionBook(store)
    actor = _actor()
    created = book.create(
        actor,
        {
            "name": "old",
            "kind": "bearer",
            "secret": "still-secret",
            "expires_at": (utcnow() - timedelta(minutes=5)).isoformat(),
        },
    )
    with pytest.raises(ArError):
        headers_for(store, actor.tenant_id, actor.user_id, "old")
    assert book.get(actor, uuid.UUID(str(created["id"])))["status"] == "expired"
    bad = book.create(
        actor,
        {
            "name": "badtoken",
            "kind": "oauth_client_credentials",
            "secret": "s",
            "token_url": "http://127.0.0.1/token",
            "client_id": "ar",
        },
    )
    failed = book.test(actor, uuid.UUID(str(bad["id"])))
    assert failed["ok"] is False


def test_oauth_token_endpoint_and_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "access_token": "live-token",
                "refresh_token": "live-refresh",
                "expires_in": "30",
            },
        )
    )
    real_client = httpx.Client
    real_async = httpx.AsyncClient

    def _client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    def _async(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_async(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _client)
    monkeypatch.setattr(httpx, "AsyncClient", _async)
    store = ChatService()
    book = ConnectionBook(store)
    actor = _actor()
    created = book.create(
        actor,
        {
            "name": "live",
            "kind": "oauth_client_credentials",
            "secret": "client-secret-value",
            "token_url": "https://example.com/token",
            "client_id": "ar",
        },
    )
    assert book.test(actor, uuid.UUID(str(created["id"])))["ok"] is True
    row = next(item for item in store.service_connections.values() if item.get("name") == "live")
    row["expires_at"] = (utcnow() - timedelta(seconds=5)).isoformat()
    headers, secret = headers_for(store, actor.tenant_id, actor.user_id, "live")
    assert secret == "live-token"
    assert headers["Authorization"] == "Bearer live-token"
    code = book.create(
        actor,
        {
            "name": "code",
            "kind": "oauth_authorization_code",
            "secret": "client-secret-value",
            "token_url": "https://example.com/token",
            "authorize_url": "https://example.com/authorize",
            "client_id": "ar",
        },
    )
    started = book.start(actor, uuid.UUID(str(code["id"])))

    async def _done() -> dict[str, object]:
        return await book.callback("auth-code", str(started["state"]))

    import asyncio

    assert asyncio.run(_done())["status"] == "active"


def test_http_import_edges() -> None:
    assert guard_public("ftp://example.com", allow=["*"], loopback=False)
    assert guard_public("https://127.0.0.1/x", allow=["*"], loopback=False)
    store = ChatService()

    def send(method: str, url: str, **_kwargs: object) -> httpx.Response:
        if url.endswith("/gone"):
            return httpx.Response(302, headers={"location": "https://example.com/spec.json"})
        if "spec.json" in url:
            return httpx.Response(
                200, text='{"openapi":"3.0.3","paths":{"/x":{"get":{"operationId":"getX"}}}}'
            )
        return httpx.Response(500, text="no")

    store.http_send = send
    raw = fetch_document(store, "https://example.com/gone")
    assert b"openapi" in raw
    with pytest.raises(ValueError):
        fetch_document(store, "https://example.com/missing")
    missing = execute_operation(store, {})
    assert missing["is_error"] is True
    no_url = execute_operation(store, {"_operation": {"method": "GET"}})
    assert no_url["code"] == "validation_failed"
    denied = execute_operation(
        store,
        {
            "_operation": {"method": "GET", "url": "https://evil.example/x"},
            "_tenant_id": demo_id("tenant"),
        },
    )
    assert denied["code"] == "egress_denied"
    filled = execute_operation(
        store,
        {
            "_operation": {
                "method": "GET",
                "baseUrl": "https://example.com",
                "path": "/pets/{id}",
                "connection": "missing",
            },
            "_tenant_id": demo_id("tenant"),
            "_user_id": demo_id("admin"),
            "id": "1",
        },
    )
    assert filled["code"] == "credential_required"
    importer = ToolImporter(store)
    with pytest.raises(ValidationFailedError):
        importer.preview_openapi({})
    with pytest.raises(ValidationFailedError):
        importer.preview_openapi({"document": '{"swagger": "2.0"}'})
    huge = {
        "openapi": "3.0.3",
        "paths": {f"/p{i}": {"get": {"operationId": f"op{i}"}} for i in range(41)},
    }
    with pytest.raises(ValidationFailedError):
        importer.import_openapi(_actor(), {"slug": "big", "document": huge})
    with pytest.raises(ValidationFailedError):
        compile_description({"description": "no url here"})


def test_stdio_and_sse_parsers() -> None:
    script = Path(sys.prefix) / "m22stdio.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.read()\n"
        'body = \'{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"ping",'
        '"inputSchema":{"type":"object"},"annotations":{"readOnlyHint":true}}]}}\'\n'
        "raw = body.encode()\n"
        "sys.stdout.buffer.write(f'Content-Length: {len(raw)}\\r\\n\\r\\n'.encode() + raw)\n",
        encoding="utf-8",
    )
    try:
        listed = list_stdio(ChatService(), [sys.executable, str(script)], timeout=20)
        assert listed[0]["name"] == "ping"
        called = call_stdio(ChatService(), [sys.executable, str(script)], "ping", {}, timeout=20)
        assert called["is_error"] is False
    finally:
        script.unlink(missing_ok=True)
    parsed = _json_from_sse(
        'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{}}\n\n', expected=2
    )
    assert parsed["id"] == 2
    framed = _frames('Content-Length: 44\r\n\r\n{"jsonrpc":"2.0","id":2,"result":{}}\n', expected=2)
    assert framed is not None
    assert safe_command([sys.executable, str(script)])[0]
    with pytest.raises(RemoteError):
        safe_command(["python", "-c", "print(1)"])
    store = ChatService()

    def send(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                text="event: endpoint\ndata: /mcp\n\n",
                headers={"content-type": "text/event-stream"},
            )
        if b"tools/list" in request.content:
            return httpx.Response(
                200,
                json={
                    "result": {"tools": [{"name": "sse_ping", "inputSchema": {"type": "object"}}]}
                },
            )
        return httpx.Response(202)

    store.mcp_transport = httpx.MockTransport(send)
    store.mcp_resolver = lambda _host: ["1.1.1.1"]
    found = list_remote(store, "https://tools.example/sse", transport="sse", timeout=5)
    assert found[0]["name"] == "sse_ping"
    store.mcp_transport = None
    with pytest.raises(RemoteError):
        list_remote(store, "https://tools.example/missing", timeout=2)


def test_refresh_reports_a_changed_manifest() -> None:
    store = ChatService()
    actor = _actor()
    calls = {"n": 0}

    def send(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        name = "ping" if calls["n"] < 4 else "pong"
        if b"tools/list" in request.content:
            return httpx.Response(
                200,
                json={
                    "result": {
                        "tools": [
                            {
                                "name": name,
                                "inputSchema": {"type": "object"},
                                "annotations": {"readOnlyHint": True},
                            }
                        ]
                    }
                },
            )
        return httpx.Response(200, json={"result": {}})

    store.mcp_transport = httpx.MockTransport(send)
    store.mcp_resolver = lambda _host: ["1.1.1.1"]
    registry = ToolRegistry(store)
    created = registry.create_server(
        actor,
        {
            "slug": "remote",
            "name": "Remote",
            "kind": "remote_mcp",
            "version": {
                "version": "1.0.0",
                "endpoint_url": "https://tools.example/mcp",
                "auth_mode": "none",
            },
        },
    )
    version_id = uuid.UUID(str(created["versions"][0]["id"]))
    tool_id = next(
        row["id"]
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "remote.ping"
    )
    registry.patch_tool(
        actor, uuid.UUID(str(created["id"])), version_id, tool_id, {"risk_class": "R0"}
    )
    registry.submit(actor, uuid.UUID(str(created["id"])), version_id)
    registry.approve(actor, uuid.UUID(str(created["id"])), version_id, "ok")
    refreshed = registry.refresh(actor, uuid.UUID(str(created["id"])))
    assert refreshed["changed"] is True

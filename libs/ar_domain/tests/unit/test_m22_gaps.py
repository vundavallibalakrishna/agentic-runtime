"""Branches the first M22 tests left dark: token errors, parsers, import edges."""

# ruff: noqa: E501, S105, S106

import asyncio
import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from ar_common.errors import ArError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.isolate import IsolatedRun, _prefixes, _probe, _process, scrubbed_env
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.describe import compile_description
from ar_domain.tools.http_tools import execute_operation, fetch_document, fetch_text, guard_public
from ar_domain.tools.imports import ToolImporter, _version_id
from ar_domain.tools.openapi_import import (
    OpenApiError,
    index_operations,
    operations_from,
    server_url,
)
from ar_domain.tools.pipeline import (
    ToolPipeline,
    _mark_mcp,
    _remote_name,
    _scrub_arguments,
    _search_mode,
)
from ar_domain.tools.registry import ToolRegistry
from ar_domain.tools.remote_mcp import (
    RemoteError,
    _frames,
    _guard,
    _json_from_sse,
    _mcp_name,
    _result_text,
    _stdio,
    _tools_from,
    auth_headers,
    call_remote,
    list_remote,
    safe_command,
)
from ar_domain.tools.service_connections import (
    ConnectionBook,
    _audit_row,
    _exchange,
    _expired,
    _headers,
    _iso,
    _open,
    _refresh_token,
    _scrub,
    _seal,
    _store_tokens,
    _token_response,
    headers_for,
)


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)


def _reader() -> Actor:
    return Actor(
        demo_id("tenant"),
        demo_id("admin"),
        frozenset(key for key in PERMISSION_KEYS if key != "tools:review"),
    )


def test_connection_edges_and_token_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    store = ChatService()
    book = ConnectionBook(store)
    actor = _actor()
    with pytest.raises(ValidationFailedError):
        book.create(actor, {"name": "plain", "kind": "bearer", "secret": ""})
    with pytest.raises(ValidationFailedError):
        book.create(
            actor,
            {
                "name": "machine",
                "kind": "oauth_client_credentials",
                "secret": "secret",
                "token_url": "",
            },
        )
    with pytest.raises(ValidationFailedError):
        book.create(
            actor,
            {
                "name": "userlogin",
                "kind": "oauth_authorization_code",
                "secret": "",
                "token_url": "memory://tokens",
            },
        )
    created = book.create(
        actor,
        {
            "name": "plain",
            "kind": "bearer",
            "secret": "sekrit-value",
            "probe_url": "https://example.com/health",
        },
    )
    listed = book.list_items(actor)
    assert listed[0]["name"] == "plain"
    updated = book.update(
        actor,
        uuid.UUID(str(created["id"])),
        {"expires_at": (utcnow() + timedelta(days=1)).isoformat(), "scopes": "nope"},
    )
    assert updated["expires_at"]
    with pytest.raises(ValidationFailedError):
        book.rotate(actor, uuid.UUID(str(created["id"])), "")
    rotated = book.rotate(actor, uuid.UUID(str(created["id"])), "rotated-secret")
    assert rotated["version"] == 2
    row = next(item for item in store.service_connections.values() if item["name"] == "plain")
    row["version"] = "legacy"
    again = book.rotate(actor, uuid.UUID(str(created["id"])), "rotated-again")
    assert again["version"] == 2
    blocked = book.test(actor, uuid.UUID(str(created["id"])), url="ftp://example.com/x")
    assert blocked["ok"] is False

    def boom(method: str, url: str, **_kwargs: object) -> httpx.Response:
        del method, url
        raise httpx.ConnectError("down")

    store.http_send = boom
    offline = book.test(actor, uuid.UUID(str(created["id"])), url="https://example.com/health")
    assert offline["error"] == "the host did not answer"

    def denied(method: str, url: str, **_kwargs: object) -> httpx.Response:
        del method, url
        return httpx.Response(503, text="rotated-again leaked")

    store.http_send = denied
    failed = book.test(actor, uuid.UUID(str(created["id"])), url="https://example.com/health")
    assert failed["ok"] is False
    assert "rotated-again" not in str(failed.get("snippet"))
    with pytest.raises(ValidationFailedError):
        book.start(actor, uuid.UUID(str(created["id"])))
    empty = {"kind": "bearer", "secret": b"", "access_token": b""}
    with pytest.raises(ArError):
        _headers(empty)
    empty["kind"] = "oauth_client_credentials"
    with pytest.raises(ArError):
        _headers(empty)
    assert _seal("") == b""
    assert _open(b"not-a-sealed-blob") == ""
    assert _open("text") == ""
    assert _scrub("sekrit", "ab") == "sekrit"
    assert _iso("plain") == "plain"
    assert _expired({"expires_at": "not-a-date"}) is False
    assert _expired({"expires_at": "2020-01-01T00:00:00"}) is False
    _audit_row(
        store,
        {
            "tenant_id": actor.tenant_id,
            "owner_user_id": actor.user_id,
            "id": created["id"],
            "name": "plain",
        },
        "connection.tested",
    )
    _store_tokens(row, {"access_token": "", "refresh_token": "", "expires_in": "soon"})

    oauth = book.create(
        actor,
        {
            "name": "userlogin",
            "kind": "oauth_authorization_code",
            "secret": "client-secret",
            "token_url": "memory://tokens",
            "authorize_url": "https://example.com/authorize",
            "client_id": "ar",
        },
    )
    started = book.start(actor, uuid.UUID(str(oauth["id"])))
    state = str(started["state"])
    store.oauth_states[state]["connection_id"] = uuid.uuid4()
    with pytest.raises(NotFoundError):
        asyncio.run(book.callback("good-code", state))
    started = book.start(actor, uuid.UUID(str(oauth["id"])))
    granted = asyncio.run(book.callback("good-code", str(started["state"])))
    assert granted["status"] == "active"
    saved = next(item for item in store.service_connections.values() if item["name"] == "userlogin")
    saved["expires_at"] = (utcnow() - timedelta(minutes=1)).isoformat()
    headers, secret = headers_for(store, actor.tenant_id, actor.user_id, "userlogin")
    assert secret.startswith("refreshed-")
    assert headers["Authorization"].startswith("Bearer ")
    saved["token_url"] = "http://127.0.0.1/token"
    saved["expires_at"] = (utcnow() - timedelta(minutes=1)).isoformat()
    with pytest.raises(ArError):
        headers_for(store, actor.tenant_id, actor.user_id, "userlogin")
    saved["token_url"] = "https://example.com/token"
    real_client = httpx.Client

    def _client(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(lambda _request: httpx.Response(500, json={}))
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _client)
    with pytest.raises(ArError):
        _token_response("https://example.com/token", {"grant_type": "client_credentials"})

    def _empty(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"token_type": "bearer"})
        )
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", _empty)
    with pytest.raises(ArError):
        _token_response("https://example.com/token", {"grant_type": "client_credentials"})
    with pytest.raises(ArError):
        asyncio.run(_exchange(saved, "invalid", "verifier"))
    saved["token_url"] = "http://169.254.169.254/token"
    with pytest.raises(ArError):
        asyncio.run(_exchange(saved, "auth-code", "verifier"))
    saved["token_url"] = "https://example.com/token"

    real_async = httpx.AsyncClient

    def _async(*_args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(lambda _request: httpx.Response(502, text="no"))
        return real_async(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "AsyncClient", _async)
    with pytest.raises(ArError):
        asyncio.run(_exchange(saved, "auth-code", "verifier"))
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *_args, **kwargs: real_async(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"token_type": "bearer"})
            ),
            **kwargs,
        ),
    )
    with pytest.raises(ArError):
        asyncio.run(_exchange(saved, "auth-code", "verifier"))
    refreshed = _refresh_token(
        {
            "name": "userlogin",
            "token_url": "memory://tokens",
            "refresh_token": saved["refresh_token"],
            "client_id": "ar",
            "secret": saved["secret"],
        }
    )
    assert refreshed["access_token"].startswith("refreshed-")


def test_http_operation_limits_and_parsers() -> None:
    assert guard_public("https://", allow=["*"], loopback=False)
    assert "allow list" in str(
        guard_public("https://evil.test/x", allow=["example.com"], loopback=False)
    )
    store = ChatService()

    def redirect(method: str, url: str, **_kwargs: object) -> httpx.Response:
        del method, url
        return httpx.Response(302, headers={"location": "https://example.com/next"})

    store.http_send = redirect
    with pytest.raises(ValueError, match="redirected"):
        fetch_document(store, "https://example.com/spec.json")

    def huge(method: str, url: str, **_kwargs: object) -> httpx.Response:
        del method, url
        return httpx.Response(200, text="x" * 2_000_001)

    store.http_send = huge
    with pytest.raises(ValueError, match="2 MB"):
        fetch_document(store, "https://example.com/spec.json")

    def raw(method: str, url: str, **_kwargs: object) -> str:
        del method, url
        return "not-a-response"

    store.http_send = raw

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def request(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(200, text="live")

        def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(200, text="doc")

    monkey = _Client
    original = httpx.Client
    httpx.Client = monkey  # type: ignore[misc]
    try:
        assert fetch_text(
            store, "POST", "https://example.com/x", json_body={"a": 1}, params={"q": None, "n": "1"}
        ) == (200, "live")
        assert fetch_document(store, "https://example.com/spec.json") == b"doc"
    finally:
        httpx.Client = original

    def down(method: str, url: str, **_kwargs: object) -> httpx.Response:
        del method, url
        raise httpx.ReadTimeout("slow")

    store.http_send = down
    failed = execute_operation(
        store,
        {
            "_operation": {"method": "GET", "url": "https://example.com/x"},
            "_tenant_id": demo_id("tenant"),
        },
    )
    assert failed["code"] == "upstream_error"
    long = execute_operation(
        store,
        {
            "_operation": {
                "method": "GET",
                "url": "https://example.com/x?q=1",
                "source": "description",
            },
            "_tenant_id": demo_id("tenant"),
            "_max_bytes": "256",
            "_timeout_s": "nope",
            "q": None,
        },
    )
    store.http_send = lambda *_args, **_kwargs: httpx.Response(200, text="y" * 4000)
    long = execute_operation(
        store,
        {
            "_operation": {
                "method": "POST",
                "url": "https://example.com/items/{id}",
                "source": "description",
            },
            "_tenant_id": demo_id("tenant"),
            "_max_bytes": 256,
            "id": "7",
            "body": {"name": "ada"},
        },
    )
    assert "truncated" in str(long["text"])
    assert long["structured"]["presentation"]["kind"] == "described"


def test_description_and_openapi_shapes() -> None:
    post = compile_description(
        {
            "description": "POST https://example.com/items using connection notes parameter sku",
            "returns": "the created item",
            "parameters": ["sku", ""],
            "slug": "Create__Item",
        }
    )
    assert post["method"] == "POST"
    assert "body" in post["input_schema"]["properties"]
    assert "Returns:" in str(post["description"])
    leading = compile_description(
        {"url": "https://example.com/x", "slug": "1abc", "method": "HEAD"}
    )
    assert str(leading["name"]).startswith("call_")
    empty = compile_description({"url": "https://example.com/x", "slug": "!!!"})
    assert empty["name"] == "call_api"
    with pytest.raises(ValidationFailedError):
        compile_description({"url": "https://example.com/x", "method": "OPTIONS"})
    document = {
        "openapi": "3.0.3",
        "servers": [{"url": "/v1"}],
        "paths": {
            "/pets": "skip",
            "/items/{id}": {
                "parameters": [{"name": "id", "in": "path"}],
                "get": {
                    "summary": "Read",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {"name": "Authorization", "in": "header"},
                        "skip",
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Item"}}
                        },
                    },
                },
                "options": {"operationId": "ignored"},
            },
        },
        "components": {"schemas": {"Item": {"type": "object"}}},
    }
    assert server_url(document, "https://example.com/openapi.json") == "https://example.com/v1"
    assert server_url({"servers": [{"url": "/v1"}]}, "") == ""
    indexed = index_operations(document)
    assert indexed["total"] == 1
    selected = operations_from(document, ["get_/items/{id}"], synthesize=True)
    assert selected[0]["method"] == "GET"
    assert "body" in selected[0]["input_schema"]["properties"]
    with pytest.raises(OpenApiError):
        operations_from(document, synthesize=False)
    with pytest.raises(OpenApiError):
        operations_from(document, ["missing"], synthesize=True)
    long_id = "A" * 60
    named = operations_from(
        {"paths": {"/x": {"get": {"operationId": long_id}}}},
        synthesize=True,
    )
    assert len(str(named[0]["name"])) <= 48
    broken = dict(document)
    broken["components"] = {}
    still = operations_from(broken, ["get_/items/{id}"], synthesize=True)
    assert still[0]["input_schema"]["properties"]["body"] == {"type": "object"}


def test_import_publish_edges() -> None:
    store = ChatService()
    importer = ToolImporter(store)
    with pytest.raises(ValidationFailedError):
        importer.preview_openapi({"document": "{}"})
    with pytest.raises(ValidationFailedError):
        importer.preview_openapi({"document": "not-json"})
    with pytest.raises(ValidationFailedError):
        importer.preview_openapi({"url": "ftp://example.com/missing"})

    def send(method: str, url: str, **_kwargs: object) -> httpx.Response:
        del method, url
        return httpx.Response(
            200, text='{"openapi":"3.0.3","paths":{"/x":{"get":{"operationId":"getX"}}}}'
        )

    store.http_send = send
    preview = importer.preview_openapi({"url": "https://example.com/openapi.json"})
    assert preview["total"] == 1
    with pytest.raises(ValidationFailedError, match="baseUrl"):
        importer.import_openapi(
            _actor(),
            {
                "slug": "nobase",
                "document": {"openapi": "3.0.3", "paths": {"/x": {"get": {"operationId": "getX"}}}},
            },
        )
    chosen = [f"op{i}" for i in range(41)]
    document = {
        "openapi": "3.0.3",
        "servers": [{"url": "https://example.com"}],
        "paths": {f"/p{i}": {"get": {"operationId": f"op{i}"}} for i in range(41)},
    }
    with pytest.raises(ValidationFailedError, match="at most"):
        importer.import_openapi(
            _actor(), {"slug": "wide", "document": document, "operations": chosen}
        )
    saved = importer.save_description(
        _reader(),
        {"description": "GET https://example.com/zen", "slug": "zen", "name": "zen"},
    )
    assert saved["status"] != "approved"
    importer.registry.submit = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        ValidationFailedError("no")
    )  # type: ignore[method-assign]
    again = importer.save_description(
        _actor(),
        {"description": "GET https://example.com/other", "slug": "other", "name": "other"},
    )
    assert again["id"]
    importer.registry.submit = ToolRegistry(store).submit  # type: ignore[method-assign]

    def _reject(*_args: object, **_kwargs: object) -> None:
        raise ArError(ErrorCode.FORBIDDEN, "no")

    importer.registry.approve = _reject  # type: ignore[method-assign]
    third = importer.save_description(
        _actor(),
        {"description": "GET https://example.com/third", "slug": "third", "name": "third"},
    )
    assert third["id"]
    importer._drop_spec({})
    importer._publish(_actor(), {"id": str(uuid.uuid4()), "versions": []})
    assert _version_id({}) is None
    assert _version_id({"versions": [{"id": "not-a-uuid"}]}) is None
    assert _version_id({"versions": []}) is None


def test_mcp_parsers_transports_and_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    assert auth_headers("none", "") == {}
    assert auth_headers("basic", "tok")["authorization"].startswith("Basic ")
    assert auth_headers("static_secret", "tok")["x-api-key"] == "tok"
    assert auth_headers("bearer", "tok")["authorization"].startswith("Bearer ")
    assert _mcp_name("Toggle--Updates") == "toggle_updates"
    assert _mcp_name("1bad") == "tool_1bad"
    assert _mcp_name("...") == ""
    with pytest.raises(RemoteError):
        _tools_from({"result": {}})
    found = _tools_from(
        {
            "result": {
                "tools": [
                    "skip",
                    {"name": ""},
                    {"name": "..."},
                    {"name": "do-thing", "annotations": "nope", "inputSchema": {"type": "object"}},
                ]
            }
        }
    )
    assert found[0]["name"] == "do_thing"
    assert (
        _result_text({"error": {"code": -32602, "message": "bad args"}})["code"] == "schema_changed"
    )
    assert (
        _result_text({"result": {"isError": True, "content": [{"text": "no"}]}})["is_error"] is True
    )
    assert _result_text({"result": {"text": "pong"}})["text"] == "pong"
    assert _frames("Content-Length: nope\r\n\r\n{}", expected=1) is None
    assert _frames('{"jsonrpc":"2.0","id":2,"result":{}}', expected=2) is not None
    assert _frames("not json\n{not", expected=None) is None
    with pytest.raises(RemoteError):
        _json_from_sse("data: not-json\n\n", expected=2)
    chosen = _json_from_sse('data: {"id": 1}\n\ndata: {"id": 2, "result": {}}\n\n', expected=2)
    assert chosen["id"] == 2
    with pytest.raises(RemoteError):
        safe_command("python")
    with pytest.raises(RemoteError):
        safe_command(["python"] * 9)
    with pytest.raises(RemoteError):
        safe_command(["python", "bad name"])
    with pytest.raises(RemoteError):
        safe_command(["rm", "-rf"])
    with pytest.raises(RemoteError):
        safe_command(["python", "--help"])
    with pytest.raises(RemoteError):
        safe_command(["python", "../secret"])
    with pytest.raises(RemoteError):
        safe_command(["npx-missing-bin"])
    with pytest.raises(RemoteError):
        _guard(ChatService(), "ftp://example.com/mcp")
    with pytest.raises(RemoteError):
        _guard(ChatService(), "https://169.254.169.254/mcp")

    store = ChatService()
    calls = {"n": 0}

    def send(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("reset")
        if b"initialize" in request.content:
            return httpx.Response(200, json={"result": {}}, headers={"mcp-session-id": "sess"})
        if b"notifications/initialized" in request.content:
            return httpx.Response(500, text="no")
        if b"tools/call" in request.content:
            return httpx.Response(
                200,
                text='data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"pong"}]}}\n\n',
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(
            200,
            json={"result": {"tools": [{"name": "ping", "inputSchema": {"type": "object"}}]}},
        )

    store.mcp_transport = httpx.MockTransport(send)
    store.mcp_resolver = lambda _host: ["1.1.1.1"]
    listed = list_remote(store, "https://tools.example/mcp", token="tok", mode="bearer")
    assert listed[0]["name"] == "ping"
    called = call_remote(store, "https://tools.example/mcp", "ping", {}, "", "none")
    assert called["text"] == "pong"
    store.mcp_transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=["nope"]))
    with pytest.raises(RemoteError):
        list_remote(store, "https://tools.example/mcp")

    def sse(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                text='event: endpoint\ndata: /messages\n\nevent: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"sse_ping","inputSchema":{"type":"object"}}]}}\n\n',
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(202)

    store.mcp_transport = httpx.MockTransport(sse)
    found = list_remote(store, "https://tools.example/sse", transport="sse", timeout=5)
    assert found[0]["name"] == "sse_ping"
    store.mcp_transport = httpx.MockTransport(
        lambda request: (
            httpx.Response(500, text="no")
            if request.method == "GET"
            else httpx.Response(200, json={})
        )
    )
    with pytest.raises(RemoteError):
        list_remote(store, "https://tools.example/sse", transport="sse", timeout=2)
    store.mcp_transport = httpx.MockTransport(
        lambda request: (
            httpx.Response(
                200, text="event: ping\ndata: hi\n\n", headers={"content-type": "text/event-stream"}
            )
            if request.method == "GET"
            else httpx.Response(200, json={})
        )
    )
    with pytest.raises(RemoteError):
        list_remote(store, "https://tools.example/sse", transport="sse", timeout=2)

    monkeypatch.setattr(
        "ar_domain.tools.remote_mcp.run_isolated",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no")),
    )
    with pytest.raises(RemoteError, match="did not start"):
        _stdio(store, [sys.executable, "-m", "missing"], {"id": 2}, timeout=1)
    monkeypatch.setattr(
        "ar_domain.tools.remote_mcp.run_isolated",
        lambda *_args, **_kwargs: IsolatedRun(1, "", "boom", False, "process"),
    )
    with pytest.raises(RemoteError, match="boom"):
        _stdio(store, [sys.executable, "-m", "missing"], {"id": 2}, timeout=1)
    monkeypatch.setattr(
        "ar_domain.tools.remote_mcp.run_isolated",
        lambda *_args, **_kwargs: IsolatedRun(0, "not a frame", "", False, "process"),
    )
    with pytest.raises(RemoteError, match="unexpected"):
        _stdio(store, [sys.executable, "-m", "missing"], {"id": 2}, timeout=1)


def test_registry_refresh_and_pipeline_helpers() -> None:
    store = ChatService()
    actor = _actor()
    registry = ToolRegistry(store)
    created = registry.create_server(
        actor,
        {
            "slug": "echo",
            "name": "Echo",
            "kind": "remote_mcp",
            "version": {"version": "1.0.0", "endpoint_url": "memory://echo"},
        },
    )
    with pytest.raises(ValidationFailedError, match="approve"):
        registry.refresh(actor, uuid.UUID(str(created["id"])))
    tool_row = next(
        item for item in store.tool_versions.values() if item.get("qualified_name") == "echo.ping"
    )
    tool_id = uuid.UUID(str(tool_row["tool_id"]))
    with pytest.raises(ValidationFailedError):
        registry.set_tool_enabled(actor, tool_id, enabled=False, reason=" ")
    with pytest.raises(NotFoundError):
        registry.set_tool_enabled(actor, tool_id, enabled=False, reason="paused")
    echo_version = uuid.UUID(str(created["versions"][0]["id"]))
    registry.patch_tool(
        actor, uuid.UUID(str(created["id"])), echo_version, tool_row["id"], {"risk_class": "R0"}
    )
    registry.submit(actor, uuid.UUID(str(created["id"])), echo_version)
    registry.approve(actor, uuid.UUID(str(created["id"])), echo_version, "ok")
    enabled = registry.set_tool_enabled(actor, tool_id, enabled=True)
    assert enabled["disabled"] is False
    disabled = registry.set_tool_enabled(actor, tool_id, enabled=False, reason="paused")
    assert disabled["status"] == "disabled"
    with pytest.raises(ValidationFailedError):
        registry.create_server(
            actor,
            {
                "slug": "local",
                "name": "Local",
                "kind": "remote_mcp",
                "version": {
                    "version": "1.0.0",
                    "endpoint_url": "stdio://sandbox",
                    "config": {"command": ["python", "-c", "print(1)"]},
                },
            },
        )
    store.mcp_resolver = lambda _host: ["1.1.1.1"]
    missing = registry.create_server(
        actor,
        {
            "slug": "needconn",
            "name": "Need",
            "kind": "remote_mcp",
            "version": {
                "version": "1.0.0",
                "endpoint_url": "https://tools.example/mcp",
                "config": {"connection": "missing"},
            },
        },
    )
    assert missing["slug"] == "needconn"
    notes = registry.create_server(
        actor,
        {
            "slug": "notes",
            "name": "Notes",
            "kind": "openapi",
            "version": {
                "version": "1.0.0",
                "config": {
                    "source": "openapi",
                    "base_url": "https://example.com",
                    "spec": {
                        "openapi": "3.0.3",
                        "paths": {"/notes": {"get": {"operationId": "listNotes"}}},
                    },
                    "openapi": {"operations": ["listNotes"]},
                },
            },
        },
    )
    version_id = uuid.UUID(str(notes["versions"][0]["id"]))
    tool = next(
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "notes.list_notes"
    )
    registry.patch_tool(
        actor, uuid.UUID(str(notes["id"])), version_id, tool["id"], {"risk_class": "R0"}
    )
    registry.submit(actor, uuid.UUID(str(notes["id"])), version_id)
    registry.approve(actor, uuid.UUID(str(notes["id"])), version_id, "ok")
    refreshed = registry.refresh(actor, uuid.UUID(str(notes["id"])))
    assert refreshed["changed"] is False
    assert (
        _remote_name({"annotations": {"_mcp_name": "do-thing"}, "name": "do_thing"}) == "do-thing"
    )
    marked = _mark_mcp({"text": "secret-value", "structured": {}}, "secret-value", "do-thing")
    assert "[redacted]" in str(marked["text"])
    assert marked["structured"]["presentation"]["kind"] == "mcp"
    hidden = _scrub_arguments(
        "general.http", {"headers": {"Authorization": "Bearer secret", "Accept": "text"}}
    )
    assert hidden["headers"]["Authorization"] == "[redacted]"
    assert hidden["headers"]["Accept"] == "text"
    assert _search_mode({}) == "auto"
    assert _search_mode({"tool_search": {"mode": "pinned"}}) == "pinned"
    pipe = ToolPipeline(store)
    promoted = pipe._effective_version(
        {"qualified_name": "general.http", "risk_class": "R0"}, {"method": "POST"}
    )
    assert promoted["risk_class"] == "W2"
    run_id = uuid.uuid4()
    message_id = uuid.uuid4()
    store.runs[run_id] = {
        "conversation_id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "input_message_id": message_id,
    }
    store.messages[message_id] = {"attachment_ids": [str(uuid.uuid4())]}
    context = pipe._sandbox_context({"run_id": run_id})
    assert context["_attachment_ids"]
    emitted: list[object] = []
    store._emit = lambda *_args, **_kwargs: emitted.append(_args)
    pipe._emit_streams(
        {"run_id": run_id, "tool_call_id": uuid.uuid4()},
        {"streams": [{"stream": "stdout", "text": "hi"}, "skip", {"stream": "nope", "text": ""}]},
    )
    assert emitted
    store.notifications = []
    failed = pipe._fail(
        {"tenant_id": actor.tenant_id, "user_id": actor.user_id},
        "credential_required",
        "connect",
        0.0,
        extra={"connect_url": "/connections"},
    )
    assert failed["error"]["code"] == "credential_required"
    assert store.notifications
    pipe._plan_event({"run_id": run_id}, {"plan": [{"step": 1}]})
    assert _prefixes()


def test_isolate_fallback_and_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    exe_dir = str(Path(sys.executable).resolve().parent)
    monkeypatch.setenv("PATH", f"{exe_dir}:/usr/bin")
    env = scrubbed_env(tmp_path / "workspace")
    assert exe_dir in env["PATH"]
    monkeypatch.setattr("ar_common.isolate.shutil.which", lambda _name: None)
    assert _probe() is False
    import subprocess

    def _expired(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="unshare", timeout=8)

    monkeypatch.setattr("ar_common.isolate.subprocess.run", _expired)
    monkeypatch.setattr("ar_common.isolate.shutil.which", lambda _name: "/usr/bin/unshare")
    assert _probe() is False
    root = tmp_path / "root"
    (root / "workspace").mkdir(parents=True)
    finished = _process(root / "workspace", [sys.executable, "-c", "print('ok')"], env, timeout=5)
    assert finished.exit_code == 0
    timed = _process(
        root / "workspace", [sys.executable, "-c", "import time; time.sleep(8)"], env, timeout=1
    )
    assert timed.exit_code == 124
    previous = os.environ.get("AR_ENV")
    os.environ["AR_ENV"] = "prod"
    try:
        with pytest.raises(RemoteError):
            _guard(ChatService(), "http://127.0.0.1/mcp")
    finally:
        if previous is None:
            os.environ.pop("AR_ENV", None)
        else:
            os.environ["AR_ENV"] = previous

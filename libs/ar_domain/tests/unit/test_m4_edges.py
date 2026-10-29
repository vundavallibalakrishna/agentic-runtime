"""Edge paths for the tool registry, handlers, credentials and the SQL guard."""

import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from ar_common.errors import ArError, ConflictError, NotFoundError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.chat_loop import maybe_tools
from ar_domain.tools.credentials import CredentialBook
from ar_domain.tools.data_connections import DataConnections
from ar_domain.tools.drift import check_drift
from ar_domain.tools.embeddings import DIMENSIONS, cosine, hash_embedding
from ar_domain.tools.handlers import dispatch
from ar_domain.tools.openapi_import import OpenApiError, load_document, operations_from
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.registry import ToolRegistry
from ar_domain.tools.remote_mcp import RemoteError, auth_headers, call_remote, list_remote
from ar_domain.tools.sql_guard import SqlRejected, check_sql

_CORPUS = Path("connectors/mcp_sql/tests/corpus/malicious.txt")


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def _store() -> ChatService:
    return ChatService()


def test_embeddings_and_sql_corpus() -> None:
    vector = hash_embedding("orders")
    assert len(vector) == DIMENSIONS
    assert cosine(vector, vector) > 0.99
    samples = [line for line in _CORPUS.read_text().splitlines() if line.strip()]
    assert len(samples) >= 200
    for sample in samples:
        with pytest.raises(SqlRejected):
            check_sql(
                sample,
                allow_tables={"public.orders"},
                deny_columns={"public.orders.password"},
            )
    with pytest.raises(SqlRejected):
        check_sql(
            "SELECT * FROM public.orders",
            allow_tables={"public.orders"},
            deny_columns={"public.orders.secret"},
        )
    limited = check_sql(
        "WITH recent AS (SELECT id FROM public.orders) SELECT id FROM recent",
        allow_tables={"public.orders"},
        deny_columns=set(),
    )
    assert "LIMIT" in limited.upper()


def test_openapi_document_errors() -> None:
    with pytest.raises(OpenApiError):
        load_document(b"not-json")
    with pytest.raises(OpenApiError):
        load_document("[]")
    with pytest.raises(OpenApiError):
        operations_from({"paths": {}})
    with pytest.raises(OpenApiError):
        operations_from({"paths": {"/x": {"get": {}}}})
    with pytest.raises(OpenApiError):
        operations_from(
            {"paths": {"/x": {"get": {"operationId": "listPets"}}}},
            selected=["missing"],
        )
    with pytest.raises(OpenApiError):
        operations_from({"paths": {"/x": {"get": {"operationId": "1bad"}}}})
    tools = operations_from(
        {
            "paths": {
                "/pets/{id}": {
                    "parameters": "skip",
                    "get": {
                        "operationId": "show_pet",
                        "parameters": [
                            {"name": "Authorization", "in": "header"},
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"$ref": "#/components/schemas/Id"},
                            },
                            "skip",
                        ],
                    },
                }
            },
            "components": {"schemas": {"Id": {"type": "string"}}},
        }
    )
    assert tools[0]["input_schema"]["properties"]["id"]["type"] == "string"


def test_registry_filters_and_lifecycle() -> None:
    store = _store()
    actor = _actor()
    book = ToolRegistry(store)
    names = book.list_servers(actor, q="ticket", kind="remote_mcp", status="approved", owner="me")
    assert names == [] or all(item["kind"] == "remote_mcp" for item in names)
    plain = book.list_servers(actor, include_builtin=False)
    assert all(item["slug"] not in {"files", "conversations"} for item in plain)
    with pytest.raises(ValidationFailedError):
        book.create_server(actor, {"slug": "Bad", "version": {}})
    with pytest.raises(ValidationFailedError):
        book.create_server(actor, {"slug": "echo2", "kind": "remote_mcp"})
    with pytest.raises(ValidationFailedError):
        book.create_server(
            actor,
            {
                "slug": "plain",
                "kind": "remote_mcp",
                "version": {"version": "1.0.0", "endpoint_url": "http://example.com/mcp"},
            },
        )
    with pytest.raises(ConflictError):
        book.create_server(
            actor,
            {
                "slug": "tickets",
                "kind": "remote_mcp",
                "version": {"version": "1.0.0", "endpoint_url": "memory://tickets"},
            },
        )
    created = book.create_server(
        actor,
        {
            "slug": "echo2",
            "name": "Echo two",
            "kind": "remote_mcp",
            "version": {"version": "1.0.0", "endpoint_url": "memory://echo", "auth_mode": "none"},
        },
    )
    server_id = uuid.UUID(str(created["id"]))
    patched = book.patch_server(actor, server_id, {"name": "Echo renamed", "description": "ping"})
    assert patched["name"] == "Echo renamed"
    versions = book.list_versions(actor, server_id)
    version_id = uuid.UUID(str(versions[0]["id"]))
    again = book.discover(actor, server_id, version_id)
    assert again["tool_count"] == 1
    tool_version_id = uuid.UUID(
        str(book.get_version(actor, server_id, version_id)["tools"][0]["id"])
    )
    book.patch_tool(
        actor,
        server_id,
        version_id,
        tool_version_id,
        {"description_override": "Say pong.", "timeout_s": 5},
    )
    with pytest.raises(ValidationFailedError):
        book.reject(actor, server_id, version_id, "  ")
    rejected = book.reject(actor, server_id, version_id, "not now")
    assert rejected["review_status"] == "rejected"
    with pytest.raises(ValidationFailedError):
        book.set_server_status(actor, server_id, "disable", "")
    disabled = book.set_server_status(actor, server_id, "disable", "maintenance")
    assert disabled["disabled"] is True
    enabled = book.set_server_status(actor, server_id, "enable")
    assert enabled["disabled"] is False
    book.delete_server(actor, server_id)
    with pytest.raises(NotFoundError):
        book.get_server(actor, server_id)
    platform = next(row for row in store.tool_servers.values() if row.get("slug") == "files")
    with pytest.raises(ArError):
        book.delete_server(actor, platform["id"])


def test_remote_discovery_and_openapi_version() -> None:
    store = _store()
    actor = _actor()

    def send(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/missing"):
            return httpx.Response(500, text="no")
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "tools": [
                        {"name": "ping", "description": "Ping", "inputSchema": {"type": "object"}}
                    ],
                    "content": [{"type": "text", "text": "remote pong"}],
                },
            },
        )

    store.mcp_transport = httpx.MockTransport(send)
    store.mcp_resolver = lambda _host: ["1.1.1.1"]
    book = ToolRegistry(store)
    created = book.create_server(
        actor,
        {
            "slug": "remote",
            "name": "Remote",
            "kind": "remote_mcp",
            "version": {
                "version": "1.0.0",
                "endpoint_url": "https://tools.example/mcp",
                "auth_mode": "static_secret",
            },
        },
    )
    assert created["versions"][0]["tool_count"] == 1
    broken = book.create_server(
        actor,
        {
            "slug": "remote_down",
            "name": "Down",
            "kind": "remote_mcp",
            "version": {"version": "1.0.0", "endpoint_url": "https://tools.example/missing"},
        },
    )
    assert broken["versions"][0]["tool_count"] == 0
    spec = {
        "openapi": "3.1.0",
        "paths": {"/pets": {"get": {"operationId": "listPets", "summary": "List"}}},
    }
    opened = book.create_server(
        actor,
        {
            "slug": "pets",
            "name": "Pets",
            "kind": "openapi",
            "version": {
                "version": "1.0.0",
                "config": {"openapi": {"spec": spec, "operations": ["listPets"]}},
            },
        },
    )
    assert opened["versions"][0]["tool_count"] == 1
    empty = book.create_server(
        actor,
        {
            "slug": "pets2",
            "name": "Pets",
            "kind": "openapi",
            "version": {"version": "1.0.0", "config": {}},
        },
    )
    assert empty["versions"][0]["discovery_error"]
    warehouse = book.create_server(
        actor,
        {
            "slug": "ledger",
            "name": "Ledger",
            "kind": "sql",
            "version": {"version": "1.0.0", "config": {"sql": {"data_connection_id": "warehouse"}}},
        },
    )
    assert warehouse["versions"][0]["tool_count"] == 3


def test_handlers_cover_each_builtin() -> None:
    file_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    store = SimpleNamespace(
        tickets=[],
        pets=[{"id": 1, "name": "doggie"}],
        files={file_id: {"name": "notes.txt", "deleted_at": None}},
        blobs={file_id: b"hello file"},
        messages={uuid.uuid4(): {"role": "user", "text": "where is the stapler"}},
        conversations={conversation_id: {}},
        tool_versions={
            uuid.uuid4(): {
                "qualified_name": "files.list",
                "description": "list files",
                "embedding": hash_embedding("files"),
            }
        },
        data_connections={},
        tenant_settings={
            demo_id("tenant"): {
                "features": {"web_fetch": True},
                "egress_allowlist": ["example.com"],
            }
        },
    )
    assert dispatch(store, "memory://nowhere", "x", {}, "")["code"] == "upstream_error"
    assert dispatch(store, "memory://tickets", "create_ticket", {"title": "a"}, "")["code"] == (
        "credential_required"
    )
    filed = dispatch(store, "memory://tickets", "create_ticket", {"title": "jam"}, "token")
    assert "TCK-" in filed["text"]
    assert "jam" in dispatch(store, "memory://tickets", "list_tickets", {}, "token")["text"]
    assert dispatch(store, "memory://tickets", "nope", {}, "token")["is_error"] is True
    assert (
        dispatch(store, "memory://tickets", "create_ticket", {}, "token")["code"]
        == "validation_failed"
    )
    assert "doggie" in dispatch(store, "memory://petstore", "list_pets", {}, "")["text"]
    assert dispatch(store, "memory://petstore", "show_pet", {"petId": 1}, "")["text"] == "doggie"
    assert dispatch(store, "memory://petstore", "show_pet", {"petId": 9}, "")["is_error"] is True
    created = dispatch(store, "memory://petstore", "create_pet", {"body": {"name": "kit"}}, "")
    assert "Created" in created["text"]
    assert "public.orders" in dispatch(store, "memory://warehouse", "list_tables", {}, "")["text"]
    described = dispatch(
        store, "memory://warehouse", "describe_table", {"table": "public.orders"}, ""
    )
    assert "sku" in described["text"]
    denied = dispatch(store, "memory://warehouse", "describe_table", {"table": "secret.t"}, "")
    assert denied["code"] == "not_allowlisted"
    counted = dispatch(
        store, "memory://warehouse", "run_query", {"sql": "SELECT count(*) FROM public.orders"}, ""
    )
    assert counted["text"] == "3"
    rejected = dispatch(store, "memory://warehouse", "run_query", {"sql": "DROP TABLE t"}, "")
    assert rejected["code"] == "sql_rejected"
    listed = dispatch(store, "builtin://files", "list", {}, "")
    assert "notes.txt" in listed["text"]
    read = dispatch(store, "builtin://files", "read", {"file_id": str(file_id), "limit": 5}, "")
    assert read["text"] == "hello"
    assert dispatch(store, "builtin://files", "read", {"file_id": "nope"}, "")["is_error"] is True
    history = dispatch(store, "builtin://conversations", "search", {"query": "stapler"}, "")
    assert "stapler" in history["text"]
    page = dispatch(store, "builtin://web", "fetch", {"url": "https://example.com/page"}, "")
    assert page["is_error"] is False
    blocked = dispatch(store, "builtin://web", "fetch", {"url": "https://evil.example/x"}, "")
    assert blocked["code"] == "egress_denied"
    assert dispatch(store, "builtin://web", "fetch", {"url": "http://example.com"}, "")["is_error"]
    plan = dispatch(
        store,
        "builtin://control",
        "plan_update",
        {"plan": ["one"], "conversation_id": conversation_id},
        "",
    )
    assert plan["text"] == "Plan updated."
    found = dispatch(store, "builtin://control", "search", {"query": "files"}, "")
    assert "files.list" in found["text"]


def test_remote_client_and_pipeline_edges() -> None:
    actor = _actor()
    assert auth_headers("none", "secret") == {}
    assert auth_headers("static_secret", "secret")["x-api-key"] == "secret"
    assert auth_headers("user_oauth", "secret")["authorization"].startswith("Bearer ")
    store = _store()

    def send(request: httpx.Request) -> httpx.Response:
        if b"tools/list" in request.content and b"empty" in request.content:
            return httpx.Response(200, json={"result": {}})
        if b"tools/call" in request.content and b"boom" in request.content:
            return httpx.Response(200, json={"error": {"message": "nope"}})
        if b"tools/call" in request.content:
            return httpx.Response(
                200,
                json={"result": {"content": [{"type": "text", "text": "remote pong"}]}},
            )
        return httpx.Response(
            200,
            json={
                "result": {
                    "tools": [
                        {
                            "name": "ping",
                            "inputSchema": {"type": "object"},
                            "annotations": {"readOnlyHint": True},
                        }
                    ]
                }
            },
        )

    store.mcp_transport = httpx.MockTransport(send)
    store.mcp_resolver = lambda _host: ["1.1.1.1"]
    listed = list_remote(store, "https://tools.example/mcp", "secret", "static_secret")
    assert listed[0]["name"] == "ping"
    called = call_remote(store, "https://tools.example/mcp", "ping", {}, "secret", "user_oauth")
    assert called["text"] == "remote pong"
    failed = call_remote(store, "https://tools.example/mcp", "boom", {"name": "boom"}, "", "none")
    assert failed["is_error"] is True
    with pytest.raises(RemoteError):
        list_remote(store, "memory://echo")
    with pytest.raises(RemoteError):
        list_remote(store, "https://169.254.169.254/mcp")
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    pipeline = ToolPipeline(store)
    limited = version.copy()
    store.tool_versions[version["id"]] = version
    version["rate_limit_per_minute"] = 1
    first = pipeline.execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "tool_version_id": version["id"],
            "arguments": {},
            "synthetic": True,
        }
    )
    assert first["status"] == "succeeded"
    second = pipeline.execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "tool_version_id": version["id"],
            "arguments": {},
            "synthetic": True,
        }
    )
    assert second["error"]["code"] == "tool_rate_limited"
    version["rate_limit_per_minute"] = 60
    store.rate_buckets.clear()
    ticket = next(
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "tickets.create_ticket"
    )
    denied = pipeline.execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "tool_version_id": ticket["id"],
            "arguments": {"title": "x"},
        }
    )
    assert denied["error"]["code"] == "not_entitled"
    del limited
    server = next(row for row in store.tool_servers.values() if row.get("slug") == "tickets")
    server_version = store.tool_server_versions[server["current_version_id"]]
    server_version["upstream_hash"] = "changed"
    drifted = pipeline.execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "tool_version_id": ticket["id"],
            "arguments": {"title": "x"},
            "synthetic": True,
        }
    )
    assert drifted["error"]["code"] == "tool_manifest_drift"
    server_version["upstream_manifest"] = {"tools": ["create_ticket", "extra"]}
    assert check_drift(store)
    ToolRegistry(store).create_server(
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
    remote = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "remote.ping"
    )
    remote_call = pipeline.execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "tool_version_id": remote["id"],
            "arguments": {},
            "synthetic": True,
        }
    )
    assert remote_call["status"] == "succeeded"
    assert "remote pong" in remote_call["result_preview"]
    assert "untrusted data" in remote_call["result_preview"]


@pytest.mark.asyncio
async def test_credentials_http_and_data_connections() -> None:
    store = _store()
    actor = _actor()

    def send(request: httpx.Request) -> httpx.Response:
        if b"refresh_token" in request.content and b"bad" in request.content:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(
            200, json={"access_token": "access-http", "refresh_token": "refresh-http"}
        )

    store.oauth_transport = httpx.MockTransport(send)
    book = CredentialBook(store)
    with pytest.raises(ValidationFailedError):
        book.create_provider(actor, {})
    created = book.create_provider(
        actor,
        {
            "slug": "desk-oauth",
            "name": "Desk",
            "kind": "oauth2",
            "authorize_url": "https://idp.example/auth",
            "token_url": "https://idp.example/token",
            "client_id": "ar",
            "default_scopes": ["tools"],
        },
    )
    provider_id = uuid.UUID(str(created["id"]))
    with pytest.raises(ConflictError):
        book.create_provider(
            actor, {"slug": "desk-oauth", "token_url": "https://idp.example/token"}
        )
    patched = book.patch_provider(actor, provider_id, {"name": "Desk OAuth"})
    assert patched["name"] == "Desk OAuth"
    started = book.start(actor, provider_id)
    assert "code_challenge" in started["authorize_url"]
    granted = await book.callback("code-1", started["state"])
    assert granted["status"] == "active"
    token = await book.access_token_for(actor, provider_id)
    assert token == "access-http"  # noqa: S105
    cached = await book.access_token_for(actor, provider_id)
    assert cached == token
    book.disconnect(actor, uuid.UUID(str(granted["id"])))
    with pytest.raises(ArError):
        await book.access_token_for(actor, provider_id)
    exchange = book.create_provider(
        actor,
        {
            "slug": "exchange",
            "kind": "token_exchange",
            "token_url": "https://idp.example/token",
            "token_exchange_audience": "tools",
        },
    )
    started_exchange = book.start(actor, uuid.UUID(str(exchange["id"])))
    await book.callback("subject", started_exchange["state"])
    book.delete_provider(actor, provider_id)
    connections = DataConnections(store)
    with pytest.raises(ValidationFailedError):
        connections.create(actor, {"name": "", "engine": "postgres"})
    made = connections.create(
        actor,
        {
            "name": "Spare",
            "engine": "postgres",
            "dsn": "memory://warehouse",
            "allowlist": {"tables": ["public.orders"], "columns_deny": ["public.orders.secret"]},
            "row_limit": 10,
        },
    )
    connection_id = uuid.UUID(str(made["id"]))
    with pytest.raises(ConflictError):
        connections.create(actor, {"name": "Spare", "engine": "postgres"})
    updated = connections.patch(
        actor, connection_id, {"schema_notes": "orders only", "status": "active"}
    )
    assert updated["schema_notes"] == "orders only"
    probed = connections.test(actor, connection_id)
    assert probed["ok"] is True
    schema = connections.schema(actor, connection_id)
    assert schema["tables"][0]["columns"]
    version = next(iter(store.tool_server_versions.values()))
    version["config"] = {"sql": {"data_connection_id": str(connection_id)}}
    with pytest.raises(ConflictError):
        connections.delete(actor, connection_id)
    version["config"] = {}
    connections.delete(actor, connection_id)
    with pytest.raises(NotFoundError):
        connections.get(actor, connection_id)


@pytest.mark.asyncio
async def test_chat_loop_skips_and_runs_a_named_tool() -> None:
    store = _store()
    run = {
        "id": uuid.uuid4(),
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "conversation_id": uuid.uuid4(),
    }
    store.events[run["id"]] = []
    assistant = {"id": uuid.uuid4()}
    assert await maybe_tools(store, run, assistant, "hello") is False
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    run["agent_version_id"] = desk["published_version_id"]
    assert await maybe_tools(store, run, assistant, "hello there") is False
    done = await maybe_tools(store, run, assistant, "/tool files.list {}")
    assert done is True
    assert (
        "files.list" in str(store.runs.get(run["id"], {}).get("result_summary", ""))
        or store.tool_calls
    )

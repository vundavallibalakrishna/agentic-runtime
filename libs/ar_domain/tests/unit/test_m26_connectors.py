"""Connector catalogue, provider calls and durable credential rows."""

from __future__ import annotations

import asyncio
import socket
import threading
import uuid

import httpx
import pytest

from ar_common.errors import NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.catalog import CONNECTORS
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.named_secrets import read_named_secret, write_named_secret
from ar_domain.tools.seed_tools import seed


def _actor(tenant: uuid.UUID | None = None) -> Actor:
    return Actor(tenant or uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)


def _store() -> ChatService:
    return ChatService()


def test_catalogue_labels_reads_and_writes() -> None:
    slugs = {item.slug for item in CONNECTORS}
    assert slugs == {
        "email",
        "slack",
        "teams",
        "gcal",
        "m365-calendar",
        "gdrive",
        "sharepoint",
        "s3",
        "jira",
        "github",
        "confluence",
        "notion",
    }
    for connector in CONNECTORS:
        assert connector.verification in {"live", "public", "not_live"}
        assert connector.verification_note
        assert connector.registration_url.startswith("https://")
        assert connector.steps
        for tool in connector.tools:
            if tool.risk == "R0":
                assert tool.kind != "email_send"
            else:
                assert tool.risk == "W2"
    notion = next(item for item in CONNECTORS if item.slug == "notion")
    assert notion.verification == "not_live"
    github = next(item for item in CONNECTORS if item.slug == "github")
    assert github.verification == "live"
    email = next(item for item in CONNECTORS if item.slug == "email")
    assert email.verification == "live"
    assert "local SMTP" in email.verification_note


def test_install_hides_the_secret_and_another_tenant_is_missing() -> None:
    store = _store()
    actor = _actor()
    book = ConnectorBook(store)
    installed = book.install(
        actor,
        "slack",
        {"secret": "xoxb-demo", "connection_name": "slack-main"},
    )
    assert "xoxb-demo" not in str(installed)
    install_id = uuid.UUID(str(installed["install"]["id"]))
    with pytest.raises(NotFoundError):
        book.get_install(_actor(), install_id)
    listed = book.list_items(actor, q="slack")
    assert listed[0]["installed"] is True
    assert book.list_items(actor, q="no-such-product") == []


def test_github_pagination_and_provider_errors() -> None:
    store = _store()
    actor = _actor()
    book = ConnectorBook(store)
    book.install(actor, "github", {"connection_name": "public"})
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.endswith("/rate_limit"):
            return httpx.Response(200, json={"rate": {"limit": 60}})
        if "page=2" in str(request.url):
            return httpx.Response(200, json=[{"name": "second"}])
        if request.url.path.endswith("/missing"):
            return httpx.Response(404, json={"message": "missing"})
        return httpx.Response(
            200,
            json=[{"name": "first"}],
            headers={"Link": '<https://api.github.com/users/octocat/repos?page=2>; rel="next"'},
        )

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    result = dispatch_connector(
        store,
        "github_list_repos",
        {"owner": "octocat", "_tenant_id": actor.tenant_id, "_user_id": actor.user_id},
    )
    assert result["is_error"] is False
    assert result["structured"]["items"][0]["name"] == "first"
    assert result["structured"]["pages"] == 2
    assert result["structured"]["items"][1]["name"] == "second"
    missing = dispatch_connector(
        store,
        "github_read_file",
        {
            "owner": "octocat",
            "repo": "hello",
            "path": "missing",
            "_tenant_id": actor.tenant_id,
            "_user_id": actor.user_id,
        },
    )
    assert "404" in str(missing["text"])


def test_status_messages_and_a_disabled_tool() -> None:
    store = _store()
    actor = _actor()
    book = ConnectorBook(store)
    detail = book.install(actor, "slack", {"secret": "xoxb-demo", "connection_name": "slack"})
    install_id = uuid.UUID(str(detail["install"]["id"]))
    book.update(actor, install_id, {"disabled_tools": ["slack_post_message"]})
    blocked = dispatch_connector(
        store,
        "slack_post_message",
        {"channel": "C1", "text": "hi", "_tenant_id": actor.tenant_id, "_user_id": actor.user_id},
    )
    assert blocked["code"] == "tool_disabled"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth.test"):
            return httpx.Response(401, json={"ok": False})
        if request.url.path.endswith("/conversations.list"):
            return httpx.Response(429, json={}, headers={"Retry-After": "12"})
        return httpx.Response(
            403,
            json={"ok": False, "error": "missing_scope"},
            headers={"X-RateLimit-Remaining": "0"},
        )

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    tested = book.test(actor, install_id)
    assert tested["ok"] is False
    assert "401" in str(tested["error"])
    limited = dispatch_connector(
        store,
        "slack_list_channels",
        {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id, "status": "429"},
    )
    assert "429" in str(limited["text"])
    assert "12" in str(limited["text"])


def test_rate_limit_stops_a_burst() -> None:
    store = _store()
    actor = _actor()
    ConnectorBook(store).install(actor, "github", {})
    store.connector_transport = httpx.MockTransport(  # type: ignore[attr-defined]
        lambda _request: httpx.Response(200, json=[])
    )
    arguments = {"owner": "octocat", "_tenant_id": actor.tenant_id, "_user_id": actor.user_id}
    for _ in range(30):
        dispatch_connector(store, "github_list_repos", arguments)
    blocked = dispatch_connector(store, "github_list_repos", arguments)
    assert blocked["code"] == "rate_limited"


def test_email_send_uses_a_local_smtp_stand_in() -> None:
    port = _smtp_stand_in()
    store = _store()
    actor = _actor()
    ConnectorBook(store).install(
        actor,
        "email",
        {
            "secret": "mailbox-secret",
            "username": "ada@example.com",
            "connection_name": "mail",
            "config": {
                "smtpHost": "127.0.0.1",
                "smtpPort": str(port),
                "smtpTls": "false",
                "fromAddress": "ada@example.com",
            },
        },
    )
    result = dispatch_connector(
        store,
        "email_send",
        {
            "to": "dev@example.com",
            "subject": "Hello",
            "body": "From the local stand-in.",
            "_tenant_id": actor.tenant_id,
            "_user_id": actor.user_id,
        },
    )
    assert result["is_error"] is False
    assert result["structured"]["to"] == "dev@example.com"


def test_s3_and_jira_shapes_use_stand_ins() -> None:
    store = _store()
    actor = _actor()
    ConnectorBook(store).install(
        actor,
        "s3",
        {
            "secret": "secret-key",
            "username": "access-key",
            "connection_name": "bucket",
            "config": {"bucket": "docs", "region": "us-east-1", "endpoint": "http://127.0.0.1:9"},
        },
    )

    class Body:
        def read(self) -> bytes:
            return b"hello object"

    class Client:
        def list_objects_v2(self, **_kwargs: object) -> dict[str, object]:
            return {"Contents": [{"Key": "notes.txt", "Size": 5}]}

        def get_object(self, **_kwargs: object) -> dict[str, object]:
            return {"Body": Body()}

        def put_object(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["Key"] == "notes.txt"
            return {}

    store.connector_s3 = Client  # type: ignore[attr-defined]
    listed = dispatch_connector(
        store, "s3_list", {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id}
    )
    assert listed["structured"]["objects"][0]["key"] == "notes.txt"
    written = dispatch_connector(
        store,
        "s3_put",
        {
            "key": "notes.txt",
            "text": "hello",
            "_tenant_id": actor.tenant_id,
            "_user_id": actor.user_id,
        },
    )
    assert written["is_error"] is False

    ConnectorBook(store).install(
        actor,
        "jira",
        {
            "secret": "token",
            "username": "ada@example.com",
            "connection_name": "jira",
            "config": {"baseUrl": "https://example.atlassian.net"},
        },
    )
    captured: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.content)
        return httpx.Response(201, json={"key": "DOC-1"})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    created = dispatch_connector(
        store,
        "jira_create_issue",
        {
            "project": "DOC",
            "summary": "Paper",
            "description": "Needed",
            "_tenant_id": actor.tenant_id,
            "_user_id": actor.user_id,
        },
    )
    assert created["is_error"] is False
    assert b"DOC" in captured[0]
    assert b"Needed" in captured[0]


def test_named_secret_and_oauth_rows_round_trip_without_plaintext() -> None:
    from ar_domain.durable.m26 import (
        load_connector_rows,
        save_credential_grants,
        save_named_secrets,
        save_oauth_states,
    )

    store = _store()
    tenant = uuid.uuid4()
    write_named_secret(store, tenant, "vendor", "super-secret")
    assert read_named_secret(store, tenant, "vendor") == "super-secret"
    row = next(iter(store.named_secrets.values()))
    assert b"super-secret" not in row["ciphertext"]

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def execute(self, statement: object, params: dict[str, object]) -> object:
            self.calls.append((str(statement), params))

            class Empty:
                def mappings(self) -> list[dict[str, object]]:
                    return []

            return Empty()

    session = Session()
    state = {
        "id": "state-1",
        "tenant_id": tenant,
        "user_id": uuid.uuid4(),
        "verifier": "plain-verifier",
        "kind": "service_connection",
        "created_at": None,
    }
    asyncio.run(save_oauth_states(session, [state]))  # type: ignore[arg-type]
    saved = session.calls[0][1]
    assert b"plain-verifier" not in bytes(saved["verifier"])  # type: ignore[arg-type]
    grant = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "user_id": uuid.uuid4(),
        "provider_id": uuid.uuid4(),
        "scopes": ["repo"],
        "status": "active",
        "access_token": "access-token",
        "refresh_token": "refresh-token",
    }
    asyncio.run(save_credential_grants(session, [grant]))  # type: ignore[arg-type]
    sealed = session.calls[1][1]
    assert b"access-token" not in bytes(sealed["access_ciphertext"])  # type: ignore[arg-type]
    asyncio.run(save_named_secrets(session, [row]))  # type: ignore[arg-type]

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def mappings(self) -> list[dict[str, object]]:
            return self._rows

    class LoadSession:
        async def execute(self, statement: object, params: dict[str, object]) -> Result:
            del params
            sql = str(statement)
            if "oauth_states" in sql:
                return Result(
                    [
                        {
                            "id": "state-1",
                            "tenant_id": tenant,
                            "user_id": state["user_id"],
                            "provider_id": None,
                            "connection_id": None,
                            "kind": "service_connection",
                            "verifier": saved["verifier"],
                        }
                    ]
                )
            if "named_secrets" in sql:
                return Result([dict(row)])
            return Result([])

    fresh = _store()
    asyncio.run(load_connector_rows(LoadSession(), fresh, tenant))  # type: ignore[arg-type]
    assert fresh.oauth_states["state-1"]["verifier"] == "plain-verifier"
    assert read_named_secret(fresh, tenant, "vendor") == "super-secret"


def test_seed_registers_connector_tools() -> None:
    store = _store()
    seed(store)
    names = {
        str(row.get("name"))
        for row in store.tool_defs.values()
        if str(row.get("qualified_name", "")).startswith("connectors.")
    }
    assert "github_read_file" in names
    assert "email_send" in names
    version = next(
        row
        for row in store.tool_versions.values()
        if row.get("name") == "email_send"
    )
    assert version["risk_class"] == "W2"


class Result:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self._rows


def _smtp_stand_in() -> int:
    """A local SMTP stand-in. It is not a customer mail provider."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.listen(1)

    def serve() -> None:
        conn, _addr = server.accept()
        with conn:
            conn.sendall(b"220 local stand-in\r\n")
            data_mode = False
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                if data_mode:
                    if b"\r\n.\r\n" in chunk:
                        conn.sendall(b"250 queued\r\n")
                        data_mode = False
                    continue
                line = chunk.split(b"\r\n", 1)[0].upper()
                if line.startswith(b"EHLO") or line.startswith(b"HELO"):
                    conn.sendall(b"250-local\r\n250 AUTH PLAIN LOGIN\r\n")
                elif line.startswith(b"AUTH"):
                    conn.sendall(b"235 ok\r\n")
                elif line.startswith(b"DATA"):
                    conn.sendall(b"354 go\r\n")
                    data_mode = True
                elif line.startswith(b"QUIT"):
                    conn.sendall(b"221 bye\r\n")
                    break
                else:
                    conn.sendall(b"250 ok\r\n")
        server.close()

    threading.Thread(target=serve, daemon=True).start()
    return port

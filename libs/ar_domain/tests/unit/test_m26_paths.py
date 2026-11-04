"""Exercise connector branches that the happy-path tests leave idle."""

from __future__ import annotations

import uuid

import httpx
import pytest

import ar_domain.connectors.tables  # noqa: F401
from ar_common.errors import NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.catalog import CONNECTORS, ToolDef
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.connectors.http import explain_status, slack_error
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.secrets.crypto import seal
from ar_domain.tools.named_secrets import read_named_secret
from ar_domain.tools.service_connections import connection_key


def _actor() -> Actor:
    return Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)


def _grant_oauth(store: ChatService) -> None:
    sealed = seal(connection_key(), b"token")
    for row in store.service_connections.values():
        if str(row.get("kind", "")).startswith("oauth"):
            row["access_token"] = sealed


def _names(tool: ToolDef) -> set[str]:
    found: set[str] = set()
    cursor = 0
    while True:
        start = tool.path.find("{", cursor)
        if start < 0:
            break
        end = tool.path.find("}", start)
        if end < 0:
            break
        found.add(tool.path[start + 1 : end])
        cursor = end + 1
    found.update(tool.required)
    found.update(tool.body)
    found.update(tool.query)
    return found


def test_status_copy() -> None:
    assert "401" in explain_status(401, {})
    assert "permission" in explain_status(403, {}).lower()
    assert "rate" in explain_status(403, {"x-ratelimit-remaining": "0"}).lower()
    assert "404" in explain_status(404, {})
    assert "12" in explain_status(429, {"retry-after": "12"})
    assert "500" in explain_status(500, {})
    assert "401" in slack_error("token_revoked")
    assert "403" in slack_error("missing_scope")
    assert "429" in slack_error("ratelimited")
    assert "404" in slack_error("channel_not_found")
    assert "Slack" in slack_error("other")


def test_every_catalog_tool_against_a_stand_in() -> None:
    store = ChatService()
    actor = _actor()
    book = ConnectorBook(store)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/README"):
            return httpx.Response(
                200,
                json={"encoding": "base64", "content": "SGVsbG8=", "path": "README"},
            )
        if request.url.path.endswith("/missing-file"):
            return httpx.Response(302, headers={"location": "https://example.com/next"})
        return httpx.Response(200, json={"ok": True, "id": "1", "name": "item"})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    for connector in CONNECTORS:
        if connector.slug in {"email", "s3"}:
            continue
        kind = "bearer" if "bearer" in connector.auth_kinds else connector.auth_kind
        book.install(
            actor,
            connector.slug,
            {
                "connection_name": connector.slug,
                "kind": kind,
                "secret": "token",
                "username": "ada@example.com",
                "client_id": "client",
                "config": {"baseUrl": "https://example.com"},
            },
        )
        _grant_oauth(store)
        for tool in connector.tools:
            arguments = dict.fromkeys(_names(tool), "value")
            arguments.update(
                {
                    "_tenant_id": actor.tenant_id,
                    "_user_id": actor.user_id,
                    "path": "README",
                    "limit": 2,
                    "maxResults": 2,
                    "pageSize": 2,
                    "per_page": 2,
                }
            )
            result = dispatch_connector(store, tool.name, arguments)
            assert result.get("code") != "unknown_tool"
    missing = dispatch_connector(store, "not_a_tool", {})
    assert missing["code"] == "unknown_tool"
    bare = dispatch_connector(store, "slack_list_channels", {})
    assert bare["code"] == "connector_not_installed"


def test_mail_and_storage_edges() -> None:
    store = ChatService()
    actor = _actor()
    book = ConnectorBook(store)
    book.install(
        actor,
        "email",
        {
            "connection_name": "mail",
            "kind": "basic",
            "username": "ada@example.com",
            "secret": "secret",
            "config": {
                "smtpHost": "127.0.0.1",
                "smtpPort": "1",
                "smtpTls": "false",
                "imapHost": "127.0.0.1",
                "imapPort": "1",
                "imapSsl": "false",
                "fromAddress": "ada@example.com",
            },
        },
    )
    args = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id}

    class Imap:
        def login(self, *_args: object) -> None:
            return None

        def select(self, _box: str) -> None:
            return None

        def search(self, *_args: object) -> tuple[str, list[bytes]]:
            return "OK", [b"1"]

        def fetch(self, item: bytes, _spec: str) -> tuple[str, list[tuple[bytes, bytes]]]:
            return "OK", [(b"", b"Subject: Hello\r\nFrom: a@b\r\nDate: today\r\n")]

        def logout(self) -> None:
            return None

    store.connector_imap = Imap  # type: ignore[attr-defined]
    listed = dispatch_connector(store, "email_list", {**args, "limit": 5})
    assert listed["is_error"] is False
    read = dispatch_connector(store, "email_read", {**args, "id": "1"})
    assert read["structured"]["subject"] == "Hello"
    missing = dispatch_connector(store, "email_read", {**args, "id": "9"})
    assert missing["is_error"] is True
    refused = dispatch_connector(
        store, "email_send", {**args, "to": "a@b.c", "subject": "s", "body": "b"}
    )
    assert refused["is_error"] is True

    book.install(
        actor,
        "s3",
        {
            "connection_name": "bucket",
            "kind": "basic",
            "username": "access",
            "secret": "secret",
            "config": {
                "endpoint": "http://169.254.169.254",
                "bucket": "docs",
                "region": "us-east-1",
            },
        },
    )
    blocked = dispatch_connector(store, "s3_list", args)
    assert blocked["is_error"] is True
    empty = dispatch_connector(store, "s3_get", args)
    assert empty["code"] == "validation_failed"


def test_uploads_pagination_and_probes() -> None:
    store = ChatService()
    actor = _actor()
    book = ConnectorBook(store)
    pages = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        pages["n"] += 1
        if "pageToken" in str(request.url):
            return httpx.Response(200, json={"files": []})
        if "cursor" in str(request.url):
            return httpx.Response(200, json={"messages": []})
        if "start=" in str(request.url):
            return httpx.Response(200, json={"results": []})
        if request.url.path.endswith("/files"):
            return httpx.Response(200, json={"files": [{"id": "1"}], "nextPageToken": "next"})
        if "conversations" in request.url.path:
            return httpx.Response(
                200,
                json={"messages": [{"text": "hi"}], "response_metadata": {"next_cursor": "c"}},
            )
        if request.url.path.endswith("/search"):
            return httpx.Response(
                200,
                json={"results": [{"id": "1"}], "size": 1, "start": 0, "limit": 1},
            )
        return httpx.Response(200, json={"id": "1"})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    book.install(
        actor,
        "gdrive",
        {"secret": "token", "connection_name": "gdrive", "client_id": "client"},
    )
    book.install(
        actor,
        "sharepoint",
        {
            "secret": "token",
            "kind": "bearer",
            "connection_name": "sharepoint",
            "client_id": "client",
        },
    )
    book.install(
        actor,
        "slack",
        {"secret": "token", "connection_name": "slack"},
    )
    book.install(
        actor,
        "confluence",
        {
            "secret": "token",
            "username": "ada@example.com",
            "connection_name": "confluence",
            "config": {"baseUrl": "https://example.com"},
        },
    )
    _grant_oauth(store)
    args = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id}
    uploaded = dispatch_connector(store, "gdrive_upload", {**args, "name": "a.txt", "text": "hi"})
    assert uploaded["is_error"] is False
    shared = dispatch_connector(store, "sharepoint_upload", {**args, "path": "a.txt", "text": "hi"})
    assert shared["is_error"] is False
    listed = dispatch_connector(store, "gdrive_list", args)
    assert listed["is_error"] is False
    history = dispatch_connector(store, "slack_read_channel", {**args, "channel": "C1"})
    assert history["is_error"] is False
    found = dispatch_connector(store, "confluence_search", {**args, "cql": "type=page"})
    assert found["is_error"] is False
    email = book.install(
        actor,
        "email",
        {"secret": "secret", "username": "ada@example.com", "connection_name": "mail"},
    )
    tested = book.test(actor, uuid.UUID(str(email["install"]["id"])))
    assert tested["ok"] is False


def test_install_updates_and_a_bad_named_secret() -> None:
    store = ChatService()
    actor = _actor()
    book = ConnectorBook(store)
    detail = book.install(
        actor,
        "jira",
        {
            "secret": "token",
            "username": "ada@example.com",
            "connection_name": "jira",
        },
    )
    install_id = uuid.UUID(str(detail["install"]["id"]))
    updated = book.update(
        actor,
        install_id,
        {
            "disabled_tools": ["jira_search", "nope"],
            "config": {"baseUrl": "https://example.com"},
            "status": "disabled",
        },
    )
    assert updated["installed"] is True
    book.remove(actor, install_id)
    with pytest.raises(NotFoundError):
        book.get_install(actor, install_id)
    store.named_secrets[(str(actor.tenant_id), "legacy")] = b"plain"
    assert read_named_secret(store, actor.tenant_id, "legacy") == "plain"
    assert read_named_secret(store, actor.tenant_id, "") is None

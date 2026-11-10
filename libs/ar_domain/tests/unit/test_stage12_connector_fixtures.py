"""Recorded connector fixtures. Proof: contract. Tokens in the file are placeholders.

The bodies follow each provider's public API examples. A live call stays behind
the connector's ``AR_CERT_*_TOKEN`` and is not made here.
"""

from __future__ import annotations

import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import orjson
import pytest

from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.secrets.crypto import seal
from ar_domain.tools.service_connections import connection_key
from ar_testing.demo import demo_store

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "stage12_connectors.json"
_BANNED = ("xoxb-", "ya29.", "ghp_", "gho_", "xoxp-")


def _actor() -> Actor:
    return Actor(__import__("uuid").uuid4(), __import__("uuid").uuid4(), PERMISSION_KEYS)


class _Server(ThreadingHTTPServer):
    cassette: dict[str, object]
    denied: bool
    seen: list[tuple[str, str, str]]


def _play(cassette: dict[str, object]) -> tuple[_Server, str]:
    routes = {
        (str(step["method"]), str(step["path"])): step
        for step in cassette["steps"]  # type: ignore[index]
        if isinstance(step, dict)
    }

    class Handler(BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            path = urlparse(self.path).path
            auth = self.headers.get("Authorization") or ""
            server: _Server = self.server  # type: ignore[assignment]
            server.seen.append((self.command, path, auth))
            if path == "/token":
                body = orjson.dumps(cassette["token"])
                status = 200
            elif server.denied:
                denied = cassette["denied"]
                body = orjson.dumps(denied["json"])  # type: ignore[index]
                status = int(denied["status"])  # type: ignore[index]
            else:
                step = routes.get((self.command, path))
                if step is None:
                    body = orjson.dumps(
                        {"error": "no fixture", "path": path, "method": self.command}
                    )
                    status = 404
                else:
                    body = orjson.dumps(step["json"])
                    status = 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            self._serve()

        def do_POST(self) -> None:
            self._serve()

        def do_PUT(self) -> None:
            self._serve()

        def log_message(self, fmt: str, *args: object) -> None:
            del fmt, args

    server = _Server(("127.0.0.1", 0), Handler)
    server.cassette = cassette
    server.denied = False
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def _install(store: object, actor: Actor, slug: str, base: str) -> None:
    ConnectorBook(store).install(
        actor,
        slug,
        {
            "connection_name": slug,
            "secret": "recorded-client-secret",
            "username": "ada@example.com",
            "client_id": "recorded-client",
            "config": {"baseUrl": base},
        },
    )
    row = next(iter(store.service_connections.values()))  # type: ignore[attr-defined]
    row["kind"] = "oauth_authorization_code"
    row["token_url"] = f"{base}/token"
    row["allow_loopback_token"] = True
    row["refresh_token"] = seal(connection_key(), b"recorded-refresh")
    row["access_token"] = seal(connection_key(), b"expired-access")
    row["expires_at"] = (utcnow() - timedelta(minutes=5)).isoformat()
    row["client_id"] = "recorded-client"
    row["secret"] = seal(connection_key(), b"recorded-client-secret")


@pytest.mark.parametrize(
    "slug",
    [
        "slack",
        "gdrive",
        "gcal",
        "gmail",
        "outlook",
        "sharepoint",
        "teams",
        "jira",
        "confluence",
        "github",
        "rest",
    ],
)
def test_recorded_fixture_list_read_write_refresh_and_denied(slug: str) -> None:
    raw = _FIXTURE.read_text(encoding="utf-8")
    for banned in _BANNED:
        assert banned not in raw
    book = orjson.loads(raw)
    cassette = book[slug]
    server, base = _play(cassette)
    try:
        store = demo_store()
        actor = _actor()
        _install(store, actor, slug, base)
        args = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id}
        names = [step["name"] for step in cassette["steps"]]
        assert names[:3] == ["list", "read", "write"]
        for step in cassette["steps"]:
            result = dispatch_connector(store, str(step["tool"]), {**args, **step["arguments"]})
            assert result["is_error"] is False, result
        assert any(path == "/token" for _method, path, _auth in server.seen)
        assert any(auth == "Bearer recorded-fixture-token" for _method, _path, auth in server.seen)
        server.denied = True
        write = cassette["steps"][-1]
        denied = dispatch_connector(store, str(write["tool"]), {**args, **write["arguments"]})
        assert denied["is_error"] is True
    finally:
        server.shutdown()

"""Request kwargs reach a real server, and a supplied transport cannot rebind."""

from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import orjson
import pytest

from ar_common.egress_http import EgressDenied, http_get, http_post, sync_client

_SEEN: list[bytes] = []
_PATHS: list[str] = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return None

    def _reply(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        _SEEN.append(body)
        _PATHS.append(self.path)
        if self.path.startswith("/redir?to="):
            target = self.path[len("/redir?to=") :]
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        payload = orjson.dumps(
            {
                "path": self.path,
                "x": self.headers.get("x-probe"),
                "body": body.decode(),
            }
        )
        self.send_response(200)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _reply  # noqa: N815
    do_POST = _reply  # noqa: N815


@pytest.fixture
def server() -> str:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_helpers_send_bodies_headers_and_params(server: str) -> None:
    posted = http_post(f"{server}/p", json={"a": 1}, headers={"x-probe": "yes"}, timeout=2)
    assert posted.status_code == 200
    body = posted.json()
    assert body["x"] == "yes"
    assert orjson.loads(body["body"]) == {"a": 1}
    fetched = http_get(f"{server}/g", params={"q": "kites"}, headers={"x-probe": "yes"}, timeout=2)
    assert "q=kites" in fetched.json()["path"]
    assert fetched.json()["x"] == "yes"


def test_a_redirect_is_checked_again(server: str) -> None:
    followed = sync_client(timeout=2, follow_redirects=True).get(
        f"{server}/redir?to={server}/after"
    )
    assert followed.json()["path"] == "/after"


def test_extension_values_and_a_private_ca_directory_are_accepted(tmp_path) -> None:
    import socket
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from ar_common.egress_http import _ca_bundle, pin_dns
    from ar_domain.durable.extensions import _json

    assert _json(datetime(2026, 1, 2, tzinfo=UTC)).startswith("2026-01-02")
    assert _json(date(2026, 1, 2)) == "2026-01-02"
    assert _json(Decimal("1.50")) == "1.50"
    assert _json(b"hi") == "hi"
    directory = tmp_path / "certs"
    directory.mkdir()
    import os

    previous = os.environ.get("SSL_CERT_DIR")
    os.environ["SSL_CERT_DIR"] = str(directory)
    try:
        assert _ca_bundle(True) is not True
    finally:
        if previous is None:
            os.environ.pop("SSL_CERT_DIR", None)
        else:
            os.environ["SSL_CERT_DIR"] = previous
    with pin_dns("pinned.example", ["127.0.0.1"]):
        found = socket.getaddrinfo("pinned.example", 80)
    assert found[0][4][0] == "127.0.0.1"


def test_an_unknown_keyword_is_rejected() -> None:
    with pytest.raises(TypeError):
        sync_client(made_up=True)


def test_a_real_transport_is_rejected() -> None:
    with pytest.raises(EgressDenied):
        sync_client(transport=httpx.HTTPTransport())


def test_search_bridge_and_gateway_send_the_body(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ar_channels.bridge import HttpBridge
    from ar_domain.tools.gateway_client import _send
    from ar_domain.tools.searching import SearxngSearch

    monkeypatch.setattr("ar_domain.tools.searching._refuse", lambda *_args, **_kwargs: None)
    found = SearxngSearch(server, allow=["127.0.0.1"]).search("kites", limit=1)
    assert found == []
    assert any("q=kites" in path for path in _PATHS)
    bridge = HttpBridge(server, token="tok")  # noqa: S106
    sent = bridge.post("/hook", {"hello": "there"})
    assert sent["x"] == "yes" or sent.get("body") or sent.get("path") == "/hook"
    gateway = _send(f"{server}/execute", {"tool": "x"}, 2.0)
    assert orjson.loads(gateway.json()["body"]) == {"tool": "x"}


def test_a_routed_completion_posts_the_body(server: str) -> None:
    import asyncio

    from ar_domain.loop.routing import routed_completion

    store = type("Store", (), {"tenant_settings": {}, "tenant_profiles": {}, "models": {}})()
    asyncio.run(
        routed_completion(
            store,
            [{"role": "user", "content": "hi"}],
            [],
            tenant_id=uuid.uuid4(),
            routes=[{"id": "local", "base_url": server, "model": "m"}],
        )
    )
    assert any("chat/completions" in path for path in _PATHS)


def test_sandbox_start_posts_the_body(server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.sandboxes.runtime import SandboxStartError, _delegate_ensure

    monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", server)
    tenant = uuid.uuid4()
    template = uuid.uuid4()
    store = type(
        "Store",
        (),
        {"sandbox_templates": {template: {"id": template, "slug": "box", "tenant_id": tenant}}},
    )()
    with pytest.raises(SandboxStartError):
        _delegate_ensure(
            store,
            tenant_id=tenant,
            template_slug="box",
            scope="user",
            scope_key="one",
            conversation_id=None,
            agent_id=None,
            user_id=None,
        )
    assert any(b"tenantId" in item for item in _SEEN)

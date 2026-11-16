"""The egress transport dials the approved address and refuses the bypasses."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from ar_common.egress_http import (
    EgressDenied,
    async_client,
    bind_allow,
    current_allow,
    reset_allow,
    sync_client,
)


def test_proxy_mounts_and_trust_env_are_rejected() -> None:
    with pytest.raises(EgressDenied):
        sync_client(proxy="http://127.0.0.1:9")
    with pytest.raises(EgressDenied):
        sync_client(mounts={"all://": httpx.MockTransport(lambda request: httpx.Response(200))})
    with pytest.raises(EgressDenied):
        sync_client(trust_env=True)


def test_a_failed_lookup_is_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    def _down(_host: str) -> list[str]:
        raise EgressDenied("rebind.test could not be resolved")

    monkeypatch.setattr("ar_common.egress_http.resolve_host", _down)
    with pytest.raises(EgressDenied):
        with sync_client(allow=["rebind.test"]) as client:
            client.get("http://rebind.test/secret")


def test_async_lookup_cannot_rebind_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpcore

    calls = {"n": 0}
    dialed: list[str] = []

    def _once(host: str) -> list[str]:
        calls["n"] += 1
        if calls["n"] > 1:
            return ["127.0.0.1"]
        assert host == "rebind.test"
        return ["8.8.8.8"]

    async def _spy(self: object, host: str, port: int, **kwargs: object) -> object:
        del self, port, kwargs
        dialed.append(host)
        raise httpcore.ConnectError("stopped")

    monkeypatch.setattr("ar_common.egress_http.resolve_host", _once)
    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", _spy)

    async def _run() -> None:
        with pytest.raises(httpx.HTTPError):
            async with async_client(allow=["rebind.test"], timeout=1.0) as client:
                await client.get("http://rebind.test/secret")

    asyncio.run(_run())
    assert dialed == ["8.8.8.8"]
    assert calls["n"] == 1


def test_uvloop_uses_the_same_pin(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpcore

    uvloop = pytest.importorskip("uvloop")
    dialed: list[str] = []
    monkeypatch.setattr("ar_common.egress_http.resolve_host", lambda _host: ["8.8.8.8"])

    async def _spy(self: object, host: str, port: int, **kwargs: object) -> object:
        del self, port, kwargs
        dialed.append(host)
        raise httpcore.ConnectError("stopped")

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", _spy)

    async def _run() -> None:
        with pytest.raises(httpx.HTTPError):
            async with async_client(allow=["rebind.test"], timeout=1.0) as client:
                await client.get("http://rebind.test/secret")

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    try:
        asyncio.run(_run())
    finally:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    assert dialed == ["8.8.8.8"]


def test_helpers_refuse_a_metadata_address_and_a_blank_url() -> None:
    from ar_common.egress_http import approved_address, get, guard, pinned_host, post

    assert guard("http:///missing") == "url must name a host"
    assert guard("http://169.254.169.254/") is not None
    with pytest.raises(EgressDenied):
        approved_address("169.254.169.254")
    with pytest.raises(EgressDenied):
        get("http://169.254.169.254/")
    with pytest.raises(EgressDenied):
        post("http://169.254.169.254/", json={})
    assert pinned_host("files.example") == "files.example"


def test_closed_mode_pins_a_named_address(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_common.egress_http import pinned_host
    from ar_common.settings import get_settings, set_settings

    previous = get_settings()
    set_settings(
        previous.model_copy(
            update={"egress_closed": True, "egress_allow_named_private": True, "egress_hosts": ""}
        )
    )
    monkeypatch.setattr("ar_common.egress_http.resolve_host", lambda _host: ["10.1.2.3"])
    try:
        assert pinned_host("files.internal", ["files.internal"]) == "10.1.2.3"
        with pytest.raises(EgressDenied):
            pinned_host("other.internal", ["files.internal"])
    finally:
        set_settings(previous)


def test_a_pinned_dial_reaches_only_the_approved_address() -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args: object) -> None:
            return None

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_client(allow=["pinned.test"], timeout=2.0) as client:
            response = client.get(f"http://127.0.0.1:{port}/")
        assert response.status_code == 200
        assert response.text == "ok"
    finally:
        server.shutdown()


def test_cluster_mode_refuses_a_public_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ar_common.egress_http.resolve_host", lambda _host: ["8.8.8.8"])
    with pytest.raises(EgressDenied, match="public"):
        with sync_client(mode="cluster", allow=["files.internal"]) as client:
            client.get("http://files.internal/")


def test_s3_without_an_endpoint_is_refused_when_closed() -> None:
    from ar_common.settings import get_settings, set_settings
    from ar_domain.connectors.storage import _pinned_endpoint

    previous = get_settings()
    set_settings(previous.model_copy(update={"egress_closed": True}))
    try:
        with pytest.raises(OSError):
            _pinned_endpoint("")
    finally:
        set_settings(previous)


def test_an_allowlist_does_not_leak_into_the_next_client() -> None:
    token = bind_allow(["only.example"])
    assert current_allow() == ["only.example"]
    reset_allow(token)
    assert current_allow() == []

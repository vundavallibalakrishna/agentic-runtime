"""A kept egress client reuses its connection, and every request is still approved."""

from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from ar_common import egress_http
from ar_common.egress_http import EgressDenied, async_client, sync_client

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Counting(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Answer)
        self.connections: set[int] = set()


class _Answer(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        server = self.server
        assert isinstance(server, _Counting)
        server.connections.add(self.client_address[1])
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args: object) -> None:
        del args


@pytest.fixture
def server() -> Iterator[_Counting]:
    egress_http._kept_sync_pools.clear()
    egress_http._kept_async_pools.clear()
    running = _Counting()
    thread = threading.Thread(target=running.serve_forever, daemon=True)
    thread.start()
    try:
        yield running
    finally:
        running.shutdown()
        running.server_close()
        egress_http._kept_sync_pools.clear()
        egress_http._kept_async_pools.clear()


def _url(server: _Counting) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/"


def test_two_kept_clients_share_one_connection(server: _Counting) -> None:
    for _ in range(3):
        with sync_client(allow=["127.0.0.1"], loopback=True, timeout=5, reuse=True) as client:
            assert client.get(_url(server)).status_code == 200
    assert len(server.connections) == 1


def test_a_client_that_is_not_kept_opens_its_own(server: _Counting) -> None:
    for _ in range(2):
        with sync_client(allow=["127.0.0.1"], loopback=True, timeout=5) as client:
            assert client.get(_url(server)).status_code == 200
    assert len(server.connections) == 2


def test_different_egress_settings_never_share_a_pool(server: _Counting) -> None:
    with sync_client(allow=["127.0.0.1"], loopback=True, timeout=5, reuse=True) as client:
        client.get(_url(server))
    with sync_client(
        allow=["127.0.0.1", "example.org"], loopback=True, timeout=5, reuse=True
    ) as client:
        client.get(_url(server))
    assert len(server.connections) == 2
    assert len(egress_http._kept_sync_pools) == 2


def test_each_request_on_a_kept_pool_is_still_approved(
    server: _Counting, monkeypatch: pytest.MonkeyPatch
) -> None:
    with sync_client(allow=["127.0.0.1"], loopback=True, timeout=5, reuse=True) as client:
        client.get(_url(server))
    # The same pool, but the egress decision now refuses the host: no request is sent.
    monkeypatch.setattr(egress_http, "_judge", lambda *_args: "refused for the test")
    with (
        sync_client(allow=["127.0.0.1"], loopback=True, timeout=5, reuse=True) as client,
        pytest.raises(EgressDenied, match="refused for the test"),
    ):
        client.get(_url(server))


def test_a_trust_store_built_for_one_call_is_not_shared() -> None:
    import ssl

    key = egress_http._reuse_key(
        ["a.example"],
        mode="external",
        loopback=None,
        verify=ssl.create_default_context(),
        http2=False,
        cert=None,
        limits=None,
    )
    assert key is None


def test_kept_async_clients_share_one_connection_on_a_loop(server: _Counting) -> None:
    async def three_calls() -> None:
        for _ in range(3):
            async with async_client(
                allow=["127.0.0.1"], loopback=True, timeout=5, reuse=True
            ) as client:
                assert (await client.get(_url(server))).status_code == 200

    asyncio.run(three_calls())
    assert len(server.connections) == 1


def test_idle_connections_are_kept_for_the_configured_time() -> None:
    from ar_common.settings import (
        BaseServiceSettings,
        get_settings,
        set_settings,
    )

    before = get_settings()
    set_settings(BaseServiceSettings(_env_file=None, egress_keepalive_s=15))
    try:
        assert egress_http._kept_limits().keepalive_expiry == 15.0
    finally:
        set_settings(before)

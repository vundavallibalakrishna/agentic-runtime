"""A customer database stays reachable on a private address in open mode."""

from __future__ import annotations

import socket
import threading
import uuid

import pytest

from ar_common.settings import get_settings, set_settings
from ar_domain.tools.database import SqlRejected, _mysql, _pin, _postgres, probe


class _Quiet(socket.socket):
    pass


def _listener() -> tuple[socket.socket, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(8)
    server.settimeout(5)

    def accept() -> None:
        while True:
            try:
                conn, _addr = server.accept()
            except OSError:
                return
            conn.close()

    threading.Thread(target=accept, daemon=True).start()
    return server, int(server.getsockname()[1])


@pytest.fixture
def mode():
    current = get_settings()

    def apply(*, closed: bool, loopback: bool = True) -> None:
        set_settings(
            current.model_copy(update={"egress_closed": closed, "egress_allow_loopback": loopback})
        )

    yield apply
    set_settings(current)


def test_open_mode_pins_a_private_address_without_refusing_it(mode) -> None:
    mode(closed=False, loopback=False)
    with _pin("10.1.2.3", []):
        pass


def test_postgres_and_mysql_reach_a_local_listener(mode) -> None:
    server, port = _listener()
    try:
        mode(closed=False)
        for engine in (_postgres, _mysql):
            with pytest.raises(Exception) as raised:
                engine(
                    f"postgresql://reader:secret@127.0.0.1:{port}/app",
                    "SELECT 1",
                    timeout_s=2,
                    limit=1,
                    params=(),
                    hosts=[],
                )
            text = str(raised.value)
            assert "deny list" not in text
            assert "allow list" not in text
        mode(closed=True, loopback=True)
        with pytest.raises(SqlRejected) as closed:
            _postgres(
                f"postgresql://reader:secret@127.0.0.1:{port}/app",
                "SELECT 1",
                timeout_s=2,
                limit=1,
                params=(),
                hosts=[],
            )
        assert "allow list" in closed.value.reason or "blocked" in closed.value.reason
        with pytest.raises(Exception) as allowed:
            _mysql(
                f"mysql://reader:secret@127.0.0.1:{port}/app",
                "SELECT 1",
                timeout_s=2,
                limit=1,
                params=(),
                hosts=["127.0.0.1"],
            )
        assert "allow list" not in str(allowed.value)
    finally:
        server.close()


def test_the_health_check_uses_the_same_rule(mode) -> None:
    server, port = _listener()
    try:
        secret = uuid.uuid4()
        tenant = uuid.uuid4()
        store = type(
            "Store",
            (),
            {
                "secret_values": {secret: f"postgresql://reader:pw@127.0.0.1:{port}/app".encode()},
                "tenant_settings": {tenant: {"egress_allowlist": ["127.0.0.1"]}},
            },
        )()
        row = {
            "dsn_secret_ref_id": secret,
            "engine": "postgres",
            "tenant_id": tenant,
            "allowlist": {},
        }
        mode(closed=False)
        opened = probe(store, row)
        assert opened["checks"][0]["ok"] is False
        assert "deny list" not in str(opened["checks"][0]["detail"])
        mode(closed=True)
        closed = probe(store, row)
        detail = str(closed["checks"][0]["detail"])
        assert "deny list" not in detail
        assert closed["checks"][1]["ok"] is True
    finally:
        server.close()

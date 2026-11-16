"""A connection string cannot steer the driver away from the host it names."""

from __future__ import annotations

import socket

import psycopg
import pymysql
import pytest

from ar_common.settings import get_settings, set_settings
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.tools.data_connections import DataConnections
from ar_domain.tools.database import SqlRejected, _dial, _refuse_unsafe
from ar_testing.demo import demo_store

_BASE = "postgresql://reader:pw@allowed.example/app"


@pytest.fixture
def mode():
    current = get_settings()

    def apply(*, closed: bool) -> None:
        set_settings(
            current.model_copy(
                update={"egress_closed": closed, "egress_allow_loopback": True}
            )
        )

    yield apply
    set_settings(current)


def _lookup(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
    address = "127.0.0.1" if host in {"allowed.example", "127.0.0.1", "10.1.2.3"} else "8.8.8.8"
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]


@pytest.fixture
def dns(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", _lookup)


@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize(
    ("suffix", "match"),
    [
        ("?host=127.0.0.1", "host"),
        ("?HOST=127.0.0.1", "host"),
        ("?hostaddr=127.0.0.1", "hostaddr"),
        ("?%68ost=127.0.0.1", "host"),
        ("?service=local", "service"),
        ("?servicefile=/tmp/pg_service.conf", "servicefile"),
        ("?unix_socket=/tmp/pg.sock", "unix_socket"),
        ("?socket=/tmp/mysql.sock", "socket"),
        ("?sslrootcert=/etc/passwd", "sslrootcert"),
        ("?options=-cstatement_timeout=0", "options"),
    ],
)
def test_a_redirecting_parameter_is_rejected(
    mode, dns, closed: bool, suffix: str, match: str
) -> None:
    del dns
    mode(closed=closed)
    with pytest.raises(SqlRejected, match=match):
        _refuse_unsafe(_BASE + suffix, {}, ["allowed.example"])


@pytest.mark.parametrize("closed", [False, True])
@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://allowed.example,127.0.0.1/app",
        "postgresql://user:pw@host1:5432,host2:5432/app",
        "postgresql://allowed.example%2C127.0.0.1/app",
        "postgresql:///app",
        "postgresql://%2Fvar%2Frun%2Fpostgresql/app",
        "postgresql://%2ftmp%2fpg.sock/app",
    ],
)
def test_a_dsn_that_does_not_name_one_host_is_rejected(mode, closed: bool, dsn: str) -> None:
    mode(closed=closed)
    with pytest.raises(SqlRejected, match=r"one host|no host|unix socket"):
        _refuse_unsafe(dsn, {}, ["allowed.example"])


def test_open_mode_connects_to_the_address_from_the_single_lookup(
    mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    mode(closed=False)
    calls = {"n": 0}

    def lookup(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        calls["n"] += 1
        address = "127.0.0.1" if calls["n"] == 1 else "10.9.9.9"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    seen: list[str] = []

    def connect(dsn: str, **_kwargs: object) -> None:
        seen.append(dsn)
        raise SqlRejected("stopped")

    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", lookup)
    monkeypatch.setattr(psycopg, "connect", connect)
    from ar_domain.tools.database import _postgres

    dial = _dial("postgresql://reader:pw@allowed.example/app", {}, [])
    with pytest.raises(SqlRejected, match="stopped"):
        _postgres(dial, "SELECT 1", timeout_s=2, limit=1, params=())
    assert calls["n"] == 1
    assert seen
    assert "hostaddr=127.0.0.1" in seen[0]
    assert "10.9.9.9" not in seen[0]


def test_mysql_is_given_the_pinned_address(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    mode(closed=False)
    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", _lookup)
    seen: dict[str, object] = {}

    def connect(**kwargs: object) -> None:
        seen.update(kwargs)
        raise SqlRejected("stopped")

    monkeypatch.setattr(pymysql, "connect", connect)
    dial = _dial("mysql://reader:pw@allowed.example/app", {}, [])
    from ar_domain.tools.database import _mysql

    with pytest.raises(SqlRejected, match="stopped"):
        _mysql(dial, "SELECT 1", timeout_s=2, limit=1, params=())
    assert seen["host"] == "127.0.0.1"


def test_creating_a_connection_rejects_a_redirecting_dsn() -> None:
    store = demo_store()
    actor = Actor(demo_id("tenant"), demo_id("admin"), frozenset({"tools:create"}))
    with pytest.raises(Exception, match="hostaddr"):
        DataConnections(store).create(
            actor,
            {
                "name": "side",
                "engine": "postgres",
                "dsn": "postgresql://reader:pw@127.0.0.1/app?hostaddr=10.0.0.1",
            },
        )

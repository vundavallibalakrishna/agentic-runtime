"""Credentials are decoded once, and TLS and the platform server are checked."""

from __future__ import annotations

import datetime
import socket
import ssl
import threading
from pathlib import Path
from urllib.parse import quote

import psycopg
import pymysql
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from psycopg.conninfo import conninfo_to_dict

from ar_common.errors import ValidationFailedError
from ar_common.settings import get_settings, set_settings
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.tools.data_connections import DataConnections
from ar_domain.tools.database import SqlRejected, _dial, _execute, _postgres
from ar_testing.demo import demo_store

_PASSWORDS = ("p!ss", "p@ss", "p%ss", "p:ss", "p/ss", "p+ss", "p ss", "päss")


@pytest.fixture
def mode():
    current = get_settings()

    def apply(**updates: object) -> None:
        set_settings(current.model_copy(update=updates))

    yield apply
    set_settings(current)


def _fake_dns(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
    address = "10.1.2.3" if ":" not in str(host) else "fd00::5"
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (address, 0))]


def _patch_dns(monkeypatch: pytest.MonkeyPatch, lookup: object) -> None:
    """Patch the resolver the dial uses, including the pin's fallback."""
    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", lookup)
    monkeypatch.setattr("ar_common.egress_http._REAL_GETADDRINFO", lookup)


@pytest.fixture
def dns(monkeypatch: pytest.MonkeyPatch):
    _patch_dns(monkeypatch, _fake_dns)


def _url(engine: str, password: str) -> str:
    return f"{engine}://user:{quote(password, safe='')}@allowed.example/app"


def test_each_driver_receives_the_password_decoded_once(
    mode, dns, monkeypatch: pytest.MonkeyPatch
) -> None:
    del dns
    mode(egress_closed=False, egress_allow_loopback=True)
    seen: dict[str, object] = {}

    def connect(**kwargs: object) -> None:
        seen.update(kwargs)
        raise SqlRejected("stopped")

    monkeypatch.setattr(pymysql, "connect", connect)
    for password in _PASSWORDS:
        dial = _dial(_url("postgresql", password), {}, [])
        assert conninfo_to_dict(dial.dsn)["password"] == password
        seen.clear()
        with pytest.raises(SqlRejected, match="stopped"):
            _execute(_url("mysql", password), "mysql", "SELECT 1", timeout_s=1, limit=1)
        assert seen["password"] == password
        assert seen["host"] == "allowed.example"
        assert seen["user"] == "user"
        assert seen["database"] == "app"


def test_an_encoded_user_and_database_are_decoded_once(
    mode, dns, monkeypatch: pytest.MonkeyPatch
) -> None:
    del dns
    mode(egress_closed=False)
    seen: dict[str, object] = {}

    def connect(**kwargs: object) -> None:
        seen.update(kwargs)
        raise SqlRejected("stopped")

    monkeypatch.setattr(pymysql, "connect", connect)
    with pytest.raises(SqlRejected, match="stopped"):
        _execute(
            "mysql://r%40x:pw@allowed.example/my%20db",
            "mysql",
            "SELECT 1",
            timeout_s=1,
            limit=1,
        )
    assert seen["user"] == "r@x"
    assert seen["database"] == "my db"


def test_a_plus_in_a_parameter_is_not_a_space(mode, dns) -> None:
    del dns
    mode(egress_closed=False)
    dial = _dial(
        "postgresql://u:pw@allowed.example/app?application_name=a+b%26host%3Devil",
        {},
        [],
    )
    assert conninfo_to_dict(dial.dsn)["application_name"] == "a+b&host=evil"


def test_tls_parameters_and_closed_mode(mode, dns, tmp_path: Path) -> None:
    del dns
    mode(egress_closed=False, egress_allow_loopback=True, db_cert_dir=str(tmp_path), ca_bundle="")
    certificate = tmp_path / "ca.pem"
    certificate.write_text("not-read-here", encoding="utf-8")
    system = _dial("postgresql://u:pw@allowed.example/app?sslrootcert=system", {}, [])
    assert system.params["sslrootcert"] == "system"
    anchored = _dial(
        f"postgresql://u:pw@allowed.example/app?sslmode=verify-full&sslrootcert={certificate}",
        {},
        [],
    )
    assert anchored.params["sslrootcert"] == str(certificate.resolve())
    with pytest.raises(SqlRejected, match="sslcert"):
        _dial(
            "postgresql://u:pw@allowed.example/app?sslcert=/etc/passwd&sslkey=/etc/passwd",
            {},
            [],
        )
    with pytest.raises(SqlRejected, match="duplicated"):
        _dial("postgresql://u:pw@allowed.example/app?sslmode=require&sslmode=disable", {}, [])
    with pytest.raises(SqlRejected, match="sslmode"):
        _dial("postgresql://u:pw@allowed.example/app?sslmode=bogus", {}, [])
    bound = _dial(
        "postgresql://u:pw@allowed.example/app?channel_binding=require"
        "&target_session_attrs=read-write&gssencmode=disable",
        {},
        [],
    )
    assert bound.params["channel_binding"] == "require"
    mode(
        egress_closed=True,
        egress_allow_loopback=True,
        egress_allow_named_private=True,
        ca_bundle=str(certificate),
    )
    closed = _dial("postgresql://u:pw@allowed.example/app", {}, ["allowed.example"])
    assert closed.params["sslmode"] == "verify-full"
    assert closed.params["sslrootcert"] == str(certificate)
    with pytest.raises(SqlRejected, match="TLS"):
        _dial(
            "postgresql://u:pw@allowed.example/app?sslmode=disable",
            {},
            ["allowed.example"],
        )


def test_mysql_verify_full_passes_a_tls_context(mode, dns, monkeypatch: pytest.MonkeyPatch) -> None:
    del dns
    mode(egress_closed=False)
    seen: dict[str, object] = {}

    def connect(**kwargs: object) -> None:
        seen.update(kwargs)
        raise SqlRejected("stopped")

    monkeypatch.setattr(pymysql, "connect", connect)
    with pytest.raises(SqlRejected, match="stopped"):
        _execute(
            "mysql://u:pw@allowed.example/app?sslmode=verify-full",
            "mysql",
            "SELECT 1",
            timeout_s=1,
            limit=1,
        )
    assert isinstance(seen["ssl"], ssl.SSLContext)
    assert seen["ssl"].check_hostname is True  # type: ignore[attr-defined]


def test_the_platform_guard_uses_the_address_and_port(
    mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    mode(egress_closed=False, egress_allow_loopback=False)
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql+asyncpg://ar:pw@ar-postgres-rw:5432/ar")

    def lookup(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.43.0.10", 0))]

    _patch_dns(monkeypatch, lookup)
    refused = [
        "postgresql://ar:pw@ar-postgres-rw:5432/ar",
        "postgresql://ar:pw@10.43.0.10:5432/ar",
        "postgresql://ar:pw@ar-postgres-rw.default.svc.cluster.local/ar",
        "postgresql://ar:pw@ar-postgres-rw/temporal",
        "postgresql://ar:pw@ar-postgres-rw/ar/x",
    ]
    for dsn in refused:
        with pytest.raises(SqlRejected, match="platform"):
            _dial(dsn, {}, [])
    with pytest.raises(SqlRejected, match="null"):
        _dial("postgresql://ar:pw@ar-postgres-rw/AR%00", {}, [])
    _dial("postgresql://ar:pw@ar-postgres-rw:5432/ar", {"allow_platform": True}, [])
    with pytest.raises(SqlRejected, match="platform"):
        _dial("postgresql://ar:pw@ar-postgres-rw:5433/other", {}, [])


def test_a_bad_port_scheme_or_keyword_dsn_is_rejected(mode) -> None:
    mode(egress_closed=False)
    store = demo_store()
    actor = Actor(demo_id("tenant"), demo_id("admin"), frozenset({"tools:create"}))
    for dsn in (
        "postgresql://u:pw@allowed.example:99999/app",
        "postgresql://u:pw@allowed.example:abc/app",
    ):
        with pytest.raises(ValidationFailedError, match="port"):
            DataConnections(store).create(actor, {"name": "bad", "engine": "postgres", "dsn": dsn})
    for dsn in ("host=evil dbname=app", "sqlite:///tmp/x.db"):
        with pytest.raises(SqlRejected, match="postgresql:// or mysql://"):
            _dial(dsn, {}, [])
    normalised = _dial("postgresql+psycopg://u:pw@10.1.2.3/app", {}, [])
    assert normalised.scheme == "postgresql"
    assert normalised.dsn.startswith("postgresql://")
    mysql = _dial("mysql+pymysql://u:pw@10.1.2.3/app", {}, [])
    assert mysql.scheme == "mysql"


def test_every_resolved_address_is_tried(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    mode(egress_closed=False, egress_allow_loopback=True)

    def lookup(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.2", 0)),
        ]

    seen: list[str] = []

    def connect(dsn: str, **_kwargs: object) -> None:
        seen.append(dsn)
        if len(seen) == 1:
            raise OSError("down")
        raise SqlRejected("stopped")

    _patch_dns(monkeypatch, lookup)
    monkeypatch.setattr(psycopg, "connect", connect)
    dial = _dial("postgresql://u:pw@allowed.example/app", {}, [])
    with pytest.raises(SqlRejected, match="stopped"):
        _postgres(dial, "SELECT 1", timeout_s=1, limit=1, params=())
    assert "hostaddr=127.0.0.1" in seen[0]
    assert "hostaddr=127.0.0.2" in seen[1]


def test_a_trailing_dot_is_stripped_from_the_tls_name(mode, dns) -> None:
    del dns
    mode(egress_closed=False)
    dial = _dial("postgresql://u:pw@allowed.example./app", {}, [])
    assert dial.host == "allowed.example"
    assert "allowed.example.:" not in dial.dsn
    upper = _dial("postgresql://u:pw@ALLOWED.EXAMPLE/app", {}, [])
    assert upper.host == "allowed.example"


def test_editing_a_connection_cannot_set_allow_platform() -> None:
    store = demo_store()
    actor = Actor(demo_id("tenant"), demo_id("admin"), frozenset({"tools:create"}))
    made = DataConnections(store).create(
        actor, {"name": "warehouse", "engine": "postgres", "dsn": "memory:demo"}
    )
    patched = DataConnections(store).patch(
        actor,
        __import__("uuid").UUID(str(made["id"])),
        {"allowlist": {"allow_platform": True, "schemas": ["public"], "tables": ["public.orders"]}},
    )
    allow = patched["allowlist"]
    assert isinstance(allow, dict)
    assert "allow_platform" not in allow
    assert allow["schemas"] == ["public"]
    assert allow["tables"] == ["public.orders"]


def _self_signed(directory: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "db.example")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=2))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("db.example")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    certificate = directory / "ca.pem"
    private = directory / "key.pem"
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return certificate, private


def test_verify_full_checks_the_name_while_dialing_the_pinned_address(
    mode, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    certificate, private = _self_signed(tmp_path)
    mode(egress_closed=False, egress_allow_loopback=True, db_cert_dir=str(tmp_path), ca_bundle="")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, private)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    port = server.getsockname()[1]
    accepted = {"n": 0}

    def serve() -> None:
        server.settimeout(5)
        while accepted["n"] < 2:
            try:
                conn, _addr = server.accept()
            except OSError:
                return
            accepted["n"] += 1
            try:
                conn.settimeout(3)
                if len(conn.recv(8)) == 8:
                    conn.sendall(b"S")
                tls = context.wrap_socket(conn, server_side=True)
                tls.close()
            except OSError:
                conn.close()

    threading.Thread(target=serve, daemon=True).start()
    _patch_dns(
        monkeypatch,
        lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    )

    def connect(host: str) -> str:
        dial = _dial(
            f"postgresql://u:pw@{host}:{port}/app?sslmode=verify-full&sslrootcert={certificate}",
            {},
            [],
        )
        assert "hostaddr=127.0.0.1" in dial.dsn
        try:
            psycopg.connect(dial.dsn, connect_timeout=3)
        except Exception as exc:  # noqa: BLE001 — the throwaway server is not Postgres
            return str(exc)
        return ""

    matched = connect("db.example")
    mismatched = connect("wrong.example")
    server.close()
    assert "translate host" not in matched.lower()
    assert "does not match" not in matched.lower()
    assert "does not match" in mismatched.lower()
    assert accepted["n"] >= 1

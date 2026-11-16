"""Dial deadline, deny-list cache, key rules, and the strict TLS floor."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from pydantic import ValidationError

from ar_common.settings import BaseServiceSettings, get_settings, set_settings
from ar_domain.tools.database import SqlRejected, _dial, _execute

_TENANT = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def mode():
    current = get_settings()

    def apply(**updates: object) -> None:
        set_settings(current.model_copy(update=updates))

    yield apply
    set_settings(current)


def _dns(monkeypatch: pytest.MonkeyPatch, table: dict[str, str]) -> None:
    def lookup(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        address = table.get(str(host), "52.1.1.1")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", lookup)
    monkeypatch.setattr("ar_common.egress_http._REAL_GETADDRINFO", lookup)


def _key_bytes(*, encrypted: bool, der: bool) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encryption = BestAvailableEncryption(b"secret") if encrypted else NoEncryption()
    encoding = Encoding.DER if der else Encoding.PEM
    return key.private_bytes(encoding, PrivateFormat.PKCS8, encryption)


def test_an_underscore_hostname_is_accepted(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    mode(egress_closed=False)
    _dns(monkeypatch, {"db_primary.corp": "52.1.1.1"})
    dial = _dial("postgresql://u:pw@db_primary.corp/app", {}, [])
    assert dial.host == "db_primary.corp"


def test_strict_mode_can_allow_verify_ca(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    mode(
        egress_closed=True,
        egress_allow_named_private=True,
        db_strict_tls=True,
        db_strict_tls_floor="verify-ca",
        ca_bundle="",
    )
    _dns(monkeypatch, {"db.example": "52.1.1.1"})
    dial = _dial("postgresql://u:pw@db.example/app?sslmode=verify-ca", {}, ["db.example"])
    assert dial.params["sslmode"] == "verify-ca"
    with pytest.raises(SqlRejected, match="TLS"):
        _dial("postgresql://u:pw@db.example/app?sslmode=require", {}, ["db.example"])


def test_postgres_rejects_charset_and_a_root_that_is_a_key(
    mode, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mode(egress_closed=False, db_cert_dir=str(tmp_path), ca_bundle="")
    _dns(monkeypatch, {"db.example": "52.1.1.1"})
    with pytest.raises(SqlRejected, match="charset"):
        _dial("postgresql://u:pw@db.example/app?charset=utf8", {}, [])
    key = tmp_path / "ca.pem"
    key.write_bytes(_key_bytes(encrypted=False, der=False))
    key.chmod(0o644)
    with pytest.raises(SqlRejected, match="not a key"):
        _dial(f"postgresql://u:pw@db.example/app?sslrootcert={key}", {}, [], tenant_id=_TENANT)


def test_key_mode_matches_libpq_and_encrypted_der_is_refused(
    mode, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mode(egress_closed=False, db_cert_dir=str(tmp_path), ca_bundle="")
    _dns(monkeypatch, {"db.example": "52.1.1.1"})
    folder = tmp_path / _TENANT
    folder.mkdir()
    cert = folder / "client.crt"
    cert.write_bytes(b"cert")
    cert.chmod(0o644)
    owned = folder / "client.key"
    owned.write_bytes(_key_bytes(encrypted=False, der=False))
    owned.chmod(0o600)
    _dial(
        f"postgresql://u:pw@db.example/app?sslcert={cert}&sslkey={owned}",
        {},
        [],
        tenant_id=_TENANT,
    )
    grouped = folder / "group.key"
    grouped.write_bytes(_key_bytes(encrypted=False, der=False))
    grouped.chmod(0o640)
    with pytest.raises(SqlRejected, match="0640"):
        _dial(
            f"postgresql://u:pw@db.example/app?sslcert={cert}&sslkey={grouped}",
            {},
            [],
            tenant_id=_TENANT,
        )
    hidden = folder / "enc.key"
    hidden.write_bytes(_key_bytes(encrypted=True, der=True))
    hidden.chmod(0o600)
    with pytest.raises(SqlRejected, match="encrypted"):
        _dial(
            f"postgresql://u:pw@db.example/app?sslcert={cert}&sslkey={hidden}",
            {},
            [],
            tenant_id=_TENANT,
        )


def test_a_bad_deny_cidr_stops_settings_and_a_lookup_miss_refuses(
    mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError, match="CIDR"):
        BaseServiceSettings(_env_file=None, platform_db_deny_cidrs="garbage")
    mode(egress_closed=False, platform_db_deny_hosts="missing.db", platform_db_deny_cidrs="")

    def down(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        if host == "missing.db":
            raise socket.gaierror("down")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.1.1.1", 0))]

    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", down)
    monkeypatch.setattr("ar_common.egress_http._REAL_GETADDRINFO", down)
    with pytest.raises(SqlRejected, match="deny list"):
        _dial("postgresql://u:pw@db.example/app", {}, [])


def test_mysql_stops_within_the_connect_deadline(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    mode(
        egress_closed=False,
        egress_allow_loopback=True,
        db_connect_deadline_s=2,
        db_max_addresses=1,
    )
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def hang() -> None:
        server.settimeout(8)
        try:
            conn, _addr = server.accept()
            time.sleep(8)
            conn.close()
        except OSError:
            return

    threading.Thread(target=hang, daemon=True).start()
    _dns(monkeypatch, {"db.example": "127.0.0.1"})
    started = time.monotonic()
    with pytest.raises(SqlRejected):
        _execute(
            f"mysql://u:pw@db.example:{port}/app",
            "mysql",
            "SELECT 1",
            timeout_s=30,
            limit=1,
        )
    elapsed = time.monotonic() - started
    server.close()
    assert elapsed < 8

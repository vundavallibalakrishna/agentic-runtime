"""Tenant certificates, the platform deny list, and dial limits."""

from __future__ import annotations

import socket
from pathlib import Path

import pymysql
import pytest
from psycopg.conninfo import conninfo_to_dict

from ar_common.settings import get_settings, set_settings
from ar_domain.tools.database import SqlRejected, _dial, _execute, _postgres

_TENANT = "11111111-1111-4111-8111-111111111111"
_OTHER = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def mode():
    current = get_settings()

    def apply(**updates: object) -> None:
        set_settings(current.model_copy(update=updates))

    yield apply
    set_settings(current)


def _patch_dns(monkeypatch: pytest.MonkeyPatch, lookup: object) -> None:
    monkeypatch.setattr("ar_domain.tools.database.socket.getaddrinfo", lookup)
    monkeypatch.setattr("ar_common.egress_http._REAL_GETADDRINFO", lookup)


def _public(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.1.1.1", 0))]


def _touch(path: Path, mode: int = 0o600, body: bytes = b"pem") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    path.chmod(mode)


def test_client_certs_stay_inside_the_tenant_directory(
    mode, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_dns(monkeypatch, _public)
    tenant = tmp_path / _TENANT
    other = tmp_path / _OTHER
    _touch(tenant / "client.crt")
    _touch(tenant / "client.key")
    _touch(other / "client.crt")
    _touch(other / "client.key")
    _touch(tmp_path / "ca.pem", mode=0o644, body=b"ca")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    link = tenant / "link.key"
    link.symlink_to(outside)
    mode(egress_closed=False, db_cert_dir=str(tmp_path), ca_bundle="", db_strict_tls=True)
    pair = (
        f"postgresql://u:pw@db.example/app?sslmode=verify-full"
        f"&sslcert={tenant / 'client.crt'}&sslkey={tenant / 'client.key'}"
    )
    dial = _dial(pair, {}, [], tenant_id=_TENANT)
    assert dial.params["sslcert"].endswith("client.crt")
    assert dial.params["sslkey"].endswith("client.key")
    shared = _dial(
        f"postgresql://u:pw@db.example/app?sslrootcert={tmp_path / 'ca.pem'}",
        {},
        [],
        tenant_id=_TENANT,
    )
    assert shared.params["sslrootcert"].endswith("ca.pem")
    system = _dial("postgresql://u:pw@db.example/app?sslrootcert=system", {}, [], tenant_id=_TENANT)
    assert system.params["sslrootcert"] == "system"
    rejected = [
        f"sslcert={other / 'client.crt'}&sslkey={other / 'client.key'}",
        f"sslcert={tenant / 'client.crt'}&sslkey={link}",
        "sslcert=client.crt&sslkey=client.key",
        f"sslcert={tenant / 'client.crt'}",
        f"sslkey={tenant / 'client.key'}",
    ]
    for query in rejected:
        with pytest.raises(SqlRejected):
            _dial(
                f"postgresql://u:pw@db.example/app?{query}",
                {},
                [],
                tenant_id=_TENANT,
            )
    loose = tenant / "loose.key"
    _touch(loose, mode=0o644)
    with pytest.raises(SqlRejected, match="sslkey"):
        _dial(
            f"postgresql://u:pw@db.example/app?sslcert={tenant / 'client.crt'}&sslkey={loose}",
            {},
            [],
            tenant_id=_TENANT,
        )
    encrypted = tenant / "enc.key"
    _touch(encrypted, body=b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n")
    with pytest.raises(SqlRejected, match="encrypted"):
        _dial(
            f"postgresql://u:pw@db.example/app?sslcert={tenant / 'client.crt'}&sslkey={encrypted}",
            {},
            [],
            tenant_id=_TENANT,
        )
    mode(db_cert_dir="", ca_bundle="/ca.pem")
    with pytest.raises(SqlRejected, match="AR_DB_CERT_DIR"):
        _dial(
            "postgresql://u:pw@db.example/app?sslcert=/etc/passwd&sslkey=/etc/shadow",
            {},
            [],
            tenant_id=_TENANT,
        )
    with pytest.raises(SqlRejected, match="sslrootcert"):
        _dial("postgresql://u:pw@db.example/app?sslrootcert=/etc/passwd", {}, [], tenant_id=_TENANT)


def test_a_bad_client_certificate_is_a_clean_error(
    mode, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_dns(monkeypatch, _public)
    tenant = tmp_path / _TENANT
    _touch(tenant / "client.crt", body=b"not a cert")
    _touch(tenant / "client.key", body=b"not a key")
    mode(egress_closed=False, db_cert_dir=str(tmp_path), ca_bundle="")

    def connect(**_kwargs: object) -> None:
        raise AssertionError("the driver must not be called")

    monkeypatch.setattr(pymysql, "connect", connect)
    with pytest.raises(SqlRejected, match="could not be loaded"):
        _execute(
            "mysql://u:pw@db.example/app?sslmode=verify-full"
            f"&sslcert={tenant / 'client.crt'}&sslkey={tenant / 'client.key'}",
            "mysql",
            "SELECT 1",
            timeout_s=1,
            limit=1,
            tenant_id=_TENANT,
        )


def test_the_deny_list_covers_sibling_services_and_pod_cidrs(
    mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    mode(
        egress_closed=False,
        egress_allow_loopback=False,
        platform_db_deny_hosts="ar-postgres-ro,ar-postgres-r,ar-postgres-rw",
        platform_db_deny_cidrs="10.42.0.0/16",
    )
    monkeypatch.setenv("AR_DATABASE_URL", "postgresql+asyncpg://ar:pw@ar-postgres-rw:5432/ar")

    def lookup(host: str, *_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        table = {
            "ar-postgres-rw": "10.43.0.10",
            "ar-postgres-ro": "10.43.0.11",
            "ar-postgres-r": "10.43.0.12",
            "db.example": "52.1.1.1",
        }
        address = table.get(host, host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    _patch_dns(monkeypatch, lookup)
    for dsn in (
        "postgresql://u:pw@ar-postgres-ro/app",
        "postgresql://u:pw@ar-postgres-r:5433/app",
        "postgresql://u:pw@10.42.1.7/app",
        "postgresql://u:pw@ar-postgres-rw:5433/app",
    ):
        with pytest.raises(SqlRejected, match="platform"):
            _dial(dsn, {}, [])
    _dial("postgresql://u:pw@db.example/app", {}, [])


def test_dial_limits_and_a_strict_host(mode, monkeypatch: pytest.MonkeyPatch) -> None:
    mode(
        egress_closed=False,
        egress_allow_loopback=True,
        db_max_addresses=4,
        db_connect_deadline_s=15,
    )

    def lookup(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (f"127.0.0.{item}", 0))
            for item in range(1, 7)
        ]

    seen: list[str] = []

    def connect(dsn: str, **_kwargs: object) -> None:
        seen.append(dsn)
        raise OSError("connection refused")

    _patch_dns(monkeypatch, lookup)
    monkeypatch.setattr("psycopg.connect", connect)
    dial = _dial("postgresql://u:pw@db.example/app", {}, [])
    with pytest.raises(SqlRejected, match="4 addresses tried"):
        _postgres(dial, "SELECT 1", timeout_s=1, limit=1, params=())
    assert len(seen) == 4
    info = conninfo_to_dict(dial.dsn)
    assert info["host"] == "db.example"
    with pytest.raises(SqlRejected, match="valid name"):
        _dial("postgresql://u:pw@x%3Fport%3D6379.example/app", {}, [])

    def auth(dsn: str, **_kwargs: object) -> None:
        raise OSError("password authentication failed")

    monkeypatch.setattr("psycopg.connect", auth)
    with pytest.raises(SqlRejected, match="authentication"):
        _postgres(dial, "SELECT 1", timeout_s=1, limit=1, params=())


def test_closed_mode_can_require_certificate_verification(
    mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dns(monkeypatch, _public)
    mode(egress_closed=True, egress_allow_named_private=True, db_strict_tls=True, ca_bundle="")
    with pytest.raises(SqlRejected, match="TLS"):
        _dial("postgresql://u:pw@db.example/app?sslmode=require", {}, ["db.example"])
    mode(db_strict_tls=False, egress_closed=True, egress_allow_named_private=True)
    dial = _dial("postgresql://u:pw@db.example/app?sslmode=require", {}, ["db.example"])
    assert dial.params["sslmode"] == "require"


def test_mysql_rejects_postgres_parameters_and_honours_connect_timeout(
    mode, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dns(monkeypatch, _public)
    mode(egress_closed=False)
    with pytest.raises(SqlRejected, match="channel_binding"):
        _dial("mysql://u:pw@db.example/app?channel_binding=require", {}, [])
    seen: dict[str, object] = {}

    def connect(**kwargs: object) -> None:
        seen.update(kwargs)
        raise SqlRejected("stopped")

    monkeypatch.setattr(pymysql, "connect", connect)
    with pytest.raises(SqlRejected, match="stopped"):
        _execute(
            "mysql://u:pw@db.example/app?connect_timeout=8",
            "mysql",
            "SELECT 1",
            timeout_s=1,
            limit=1,
        )
    assert seen["connect_timeout"] == 8


def test_the_chart_names_platform_services_and_can_isolate_the_pooler() -> None:
    root = Path(__file__).resolve()
    while not (root / "deploy/helm/agentic-runtime").is_dir():
        root = root.parent
    policy = (root / "deploy/helm/agentic-runtime/templates/networkpolicy.yaml").read_text(
        encoding="utf-8"
    )
    config = (root / "deploy/helm/agentic-runtime/templates/configmap.yaml").read_text(
        encoding="utf-8"
    )
    overlay = (root / "deploy/helm/agentic-runtime/values-airgap.yaml").read_text(encoding="utf-8")
    assert "isolatePlatformDb" in policy
    assert "cnpg.io/podRole: pooler" in policy
    assert "-pg-rw" in config
    assert "-pg-ro" in config
    assert "isolatePlatformDb: true" in overlay

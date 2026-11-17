"""An existing superuser role becomes the install-secret role."""

from __future__ import annotations

import asyncio
import subprocess
import time

import asyncpg
import pytest

from ar_domain.db.reconcile_roles import main

pytestmark = pytest.mark.integration

_PORT = 55439
_IMAGE_PASSWORD = "image-super-secret"  # noqa: S105
_OWNER = "owner-upgrade-secret"
_APP = "app-upgrade-secret"
_PLATFORM = "platform-upgrade-secret"
_READONLY = "readonly-upgrade-secret"


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )


def test_existing_superuser_role_is_reconciled(monkeypatch: pytest.MonkeyPatch) -> None:
    name = "ar-role-upgrade"
    _docker("rm", "-f", name)
    started = _docker(
        "run",
        "-d",
        "--name",
        name,
        "-e",
        "POSTGRES_USER=postgres",
        "-e",
        f"POSTGRES_PASSWORD={_IMAGE_PASSWORD}",
        "-e",
        "POSTGRES_DB=agentic_runtime",
        "-p",
        f"{_PORT}:5432",
        "pgvector/pgvector:0.8.7-pg18-trixie",
    )
    if started.returncode != 0:
        pytest.fail(started.stderr)
    try:
        ready = False
        for _ in range(40):
            probe = _docker("exec", name, "pg_isready", "-U", "postgres", "-d", "agentic_runtime")
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(1)
        if not ready:
            pytest.fail(_docker("logs", name).stderr)
        created = _docker(
            "exec",
            name,
            "psql",
            "-U",
            "postgres",
            "-d",
            "agentic_runtime",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "CREATE ROLE ar_owner LOGIN SUPERUSER PASSWORD 'ar_owner';"
            "CREATE ROLE ar_app LOGIN PASSWORD 'ar_app';"
            "CREATE ROLE ar_platform LOGIN PASSWORD 'ar_platform';"
            "CREATE ROLE ar_readonly LOGIN PASSWORD 'ar_readonly';",
        )
        if created.returncode != 0:
            pytest.fail(created.stderr or created.stdout)
        monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
        monkeypatch.setenv("POSTGRES_PORT", str(_PORT))
        monkeypatch.setenv("POSTGRES_USER", "postgres")
        monkeypatch.setenv("POSTGRES_PASSWORD", _IMAGE_PASSWORD)
        monkeypatch.setenv("POSTGRES_DB", "agentic_runtime")
        monkeypatch.setenv("AR_ENV", "dev")
        monkeypatch.setenv("AR_DB_OWNER_PASSWORD", _OWNER)
        monkeypatch.setenv("AR_DB_APP_PASSWORD", _APP)
        monkeypatch.setenv("AR_DB_PLATFORM_PASSWORD", _PLATFORM)
        monkeypatch.setenv("AR_DB_READONLY_PASSWORD", _READONLY)
        main()
        main()
        asyncio.run(_assert_roles())
    finally:
        _docker("rm", "-f", name)


async def _assert_roles() -> None:
    connection = await asyncpg.connect(
        user="ar_owner",
        password=_OWNER,
        host="127.0.0.1",
        port=_PORT,
        database="agentic_runtime",
    )
    try:
        row = await connection.fetchrow(
            "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
            "FROM pg_roles WHERE rolname = 'ar_owner'"
        )
    finally:
        await connection.close()
    assert row is not None
    assert row["rolsuper"] is False
    assert row["rolcreatedb"] is False
    assert row["rolcreaterole"] is False
    assert row["rolbypassrls"] is True
    with pytest.raises(asyncpg.InvalidPasswordError):
        await asyncpg.connect(
            user="ar_owner",
            password="ar_owner",  # noqa: S106
            host="127.0.0.1",
            port=_PORT,
            database="agentic_runtime",
        )

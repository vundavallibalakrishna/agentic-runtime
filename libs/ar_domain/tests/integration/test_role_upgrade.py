"""An existing superuser role becomes the install-secret role."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

import asyncpg
import pytest

pytestmark = pytest.mark.integration

_PORT = 55439
_IMAGE_PASSWORD = "image-super-secret"  # noqa: S105
_OWNER = "owner-upgrade-secret"
_APP = "app-upgrade-secret"
_PLATFORM = "platform-upgrade-secret"
_READONLY = "readonly-upgrade-secret"
_TEMPORAL = "temporal-upgrade-secret"


def _docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("shape", "user", "old_password", "sql"),
    [
        (
            "statefulset",
            "ar_app",
            "ar-install-db",
            "CREATE ROLE ar_app LOGIN SUPERUSER PASSWORD 'ar-install-db';"
            "CREATE ROLE ar_owner LOGIN SUPERUSER PASSWORD 'ar_owner';"
            "CREATE ROLE ar_platform LOGIN PASSWORD 'ar_platform';"
            "CREATE ROLE ar_readonly LOGIN PASSWORD 'ar_readonly';",
        ),
        (
            "compose",
            "ar_owner",
            "ar_owner",
            "CREATE ROLE ar_owner LOGIN SUPERUSER PASSWORD 'ar_owner';"
            "CREATE ROLE ar_app LOGIN PASSWORD 'ar_app';"
            "CREATE ROLE ar_platform LOGIN PASSWORD 'ar_platform';"
            "CREATE ROLE ar_readonly LOGIN PASSWORD 'ar_readonly';",
        ),
    ],
)
def test_old_superuser_login_is_reconciled_in_prod(
    shape: str,
    user: str,
    old_password: str,
    sql: str,
) -> None:
    name = f"ar-role-upgrade-{shape}"
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
            # Over TCP. While the image runs its first-start scripts a temporary server
            # answers on the socket only, then shuts down; the real one listens on TCP.
            probe = _docker(
                "exec",
                name,
                "pg_isready",
                "-h",
                "127.0.0.1",
                "-U",
                "postgres",
                "-d",
                "agentic_runtime",
            )
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
            sql,
        )
        if created.returncode != 0:
            pytest.fail(created.stderr or created.stdout)

        async def _probe() -> None:
            connection = await asyncpg.connect(
                user=user,
                password=old_password,
                host="127.0.0.1",
                port=_PORT,
                database="agentic_runtime",
            )
            await connection.close()

        try:
            asyncio.run(_probe())
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"old login rejected before reconciliation: {type(exc).__name__}")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV", ""),
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": str(_PORT),
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": old_password,
            "POSTGRES_DB": "agentic_runtime",
            "AR_ENV": "prod",
            "AR_DB_RECONCILE": "run",
            "AR_DB_OWNER_PASSWORD": _OWNER,
            "AR_DB_APP_PASSWORD": _APP,
            "AR_DB_PLATFORM_PASSWORD": _PLATFORM,
            "AR_DB_READONLY_PASSWORD": _READONLY,
            "AR_DB_TEMPORAL_PASSWORD": _TEMPORAL,
        }
        command = [sys.executable, "-c", "from ar_domain.db.reconcile_roles import main; main()"]
        first = subprocess.run(command, check=False, capture_output=True, env=env, text=True)  # noqa: S603
        if first.returncode != 0:
            pytest.fail(first.stderr or first.stdout)
        # The old login is an application role. Reconciliation removes SUPERUSER
        # and replaces its password, so the next run uses the image superuser
        # that the chart keeps (POSTGRES_USER=postgres).
        again = dict(env)
        again["POSTGRES_USER"] = "postgres"
        again["POSTGRES_PASSWORD"] = _IMAGE_PASSWORD
        second = subprocess.run(command, check=False, capture_output=True, env=again, text=True)  # noqa: S603
        if second.returncode != 0:
            pytest.fail(second.stderr or second.stdout)
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

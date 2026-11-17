"""Create the Temporal databases as the Postgres superuser, or check the role can connect.

Bundled CloudNativePG and the StatefulSet pass ``AR_TEMPORAL_ENSURE=superuser``.
The login is the image or operator superuser, the same secret the chart already
uses for role reconciliation. An external database passes ``check``: the
databases must already exist and be owned by ``ar_temporal``.

The command retries until the login works, so a new role password is not used
before CloudNativePG has reconciled it. Passwords are not written to stderr.
"""

from __future__ import annotations

import os
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from ar_common.database_roles import PASSWORD_ENV, role_password
from ar_domain.db.role_admin import ensure_temporal_databases, temporal_database_names

_DEFAULT_WAIT_S = 600.0


def main() -> None:
    """Console entry. ``superuser`` creates the databases. ``check`` only connects."""
    mode = os.environ.get("AR_TEMPORAL_ENSURE", "check").strip().casefold() or "check"
    if mode not in {"superuser", "check"}:
        sys.stderr.write("AR_TEMPORAL_ENSURE must be superuser or check\n")
        raise SystemExit(1)
    wait_s = _wait_seconds()
    try:
        temporal_database_names()
        if mode == "superuser":
            _wait(wait_s, _ensure)
            return
        _wait(wait_s, _check)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {_redact(str(exc))}"
        sys.stderr.write(f"temporal database setup failed: {detail[:300]}\n")
        raise SystemExit(1) from None


def _ensure() -> None:
    login = _superuser()
    engine = create_engine(_url(login), isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with engine.connect() as connection:
            ensure_temporal_databases(connection)
    finally:
        engine.dispose()


def _check() -> None:
    password = role_password("ar_temporal")
    host = os.environ.get("POSTGRES_HOST", "").strip()
    if not host:
        message = "POSTGRES_HOST is required"
        raise RuntimeError(message)
    port = int(os.environ.get("POSTGRES_PORT", "5432").strip() or "5432")
    for database in temporal_database_names():
        engine = create_engine(
            _url(
                {
                    "user": "ar_temporal",
                    "password": password,
                    "host": host,
                    "port": port,
                    "database": database,
                }
            ),
            poolclass=NullPool,
        )
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()


def _superuser() -> dict[str, object]:
    user = os.environ.get("POSTGRES_USER", "").strip()
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "").strip()
    if not user or not password or not host:
        message = "POSTGRES_USER, POSTGRES_PASSWORD and POSTGRES_HOST are required"
        raise RuntimeError(message)
    port = int(os.environ.get("POSTGRES_PORT", "5432").strip() or "5432")
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": os.environ.get("POSTGRES_DB", "postgres").strip() or "postgres",
    }


def _url(login: dict[str, object]) -> URL:
    port = login["port"]
    if not isinstance(port, int):
        message = "database port must be an integer"
        raise TypeError(message)
    return URL.create(
        drivername="postgresql+psycopg",
        username=str(login["user"]),
        password=str(login["password"]),
        host=str(login["host"]),
        port=port,
        database=str(login["database"]),
    )


def _wait(wait_s: float, action: object) -> None:
    deadline = time.monotonic() + wait_s
    last = "database did not answer"
    while time.monotonic() < deadline:
        try:
            action()  # type: ignore[operator]
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {_redact(str(exc))}"
            time.sleep(2)
            continue
        return
    sys.stderr.write(f"temporal database was not ready: {last[:300]}\n")
    raise SystemExit(1)


def _wait_seconds() -> float:
    raw = os.environ.get("AR_SCHEMA_WAIT_S", "").strip() or str(_DEFAULT_WAIT_S)
    try:
        value = float(raw)
    except ValueError:
        sys.stderr.write("AR_SCHEMA_WAIT_S is not a number\n")
        raise SystemExit(1) from None
    if value <= 0:
        sys.stderr.write("AR_SCHEMA_WAIT_S must be positive\n")
        raise SystemExit(1)
    return value


def _redact(message: str) -> str:
    redacted = message
    for name in (*PASSWORD_ENV.values(), "POSTGRES_PASSWORD", "POSTGRES_PWD", "SQL_PASSWORD"):
        secret = os.environ.get(name, "")
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    line = redacted.splitlines()[0] if redacted else ""
    return line[:300]


if __name__ == "__main__":
    main()

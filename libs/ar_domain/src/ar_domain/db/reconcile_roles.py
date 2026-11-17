"""Reconcile application roles as the database superuser.

Existing volumes keep the previous chart's roles (``ar_owner`` is ``SUPERUSER``
and the other passwords are the role names). This command runs
``apply_database_roles`` on a superuser connection before migrations and the
app read the new secret. Running it again changes nothing.

``POSTGRES_USER`` / ``POSTGRES_PASSWORD`` are the superuser that can log in
today. On a volume from the previous chart that is ``ar_app`` / ``ar-install-db``
or ``ar_owner`` / ``ar_owner``. Those values are not application passwords, so
the placeholder check does not apply to them. The new role passwords are the
``AR_DB_*_PASSWORD`` keys of the install secret.
"""

from __future__ import annotations

import os
import sys
from typing import TypedDict
from urllib.parse import urlsplit

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.pool import StaticPool

from ar_common.database_roles import APPLICATION_ROLES, PASSWORD_ENV, role_password
from ar_domain.db.role_admin import apply_database_roles, ensure_temporal_databases


class _Login(TypedDict):
    user: str
    password: str
    host: str
    port: int
    database: str


def _login() -> _Login:
    """The current superuser, from the environment. The password stays out of argv."""
    explicit = os.environ.get("AR_DB_SUPERUSER_URL", "").strip()
    if explicit:
        parsed = make_url(explicit)
        if not parsed.username or parsed.password is None:
            message = "AR_DB_SUPERUSER_URL needs a username and password"
            raise RuntimeError(message)
        return {
            "user": parsed.username,
            "password": parsed.password,
            "host": parsed.host or "127.0.0.1",
            "port": parsed.port or 5432,
            "database": parsed.database or "agentic_runtime",
        }
    user = os.environ.get("POSTGRES_USER", "").strip() or "postgres"
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    database = os.environ.get("POSTGRES_DB", "agentic_runtime").strip() or "agentic_runtime"
    port_text = os.environ.get("POSTGRES_PORT", "").strip()
    port_text = port_text or os.environ.get("AR_PG_HOST_PORT", "").strip() or "5432"
    if not password:
        message = "POSTGRES_USER and POSTGRES_PASSWORD are required"
        raise RuntimeError(message)
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": int(port_text),
        "database": database,
    }


def _redact(message: str) -> str:
    redacted = message
    for name in (*PASSWORD_ENV.values(), "POSTGRES_PASSWORD"):
        secret = os.environ.get(name, "")
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    line = redacted.splitlines()[0] if redacted else ""
    return line[:300]


def _engine() -> Engine:
    """One pooled connection. The session role's password can change."""
    login = _login()
    url = URL.create(
        drivername="postgresql+psycopg",
        username=login["user"],
        password=login["password"],
        host=login["host"],
        port=login["port"],
        database=login["database"],
    )
    return create_engine(url, poolclass=StaticPool)


def _run() -> None:
    engine = _engine()
    # CREATE DATABASE cannot run in the role transaction. Do it first.
    autocommit = create_engine(engine.url, isolation_level="AUTOCOMMIT", poolclass=StaticPool)
    try:
        with autocommit.connect() as connection:
            ensure_temporal_databases(connection)
        with engine.connect() as connection:
            _apply(connection)
            connection.commit()
    finally:
        autocommit.dispose()
        engine.dispose()


def _apply(connection: object) -> None:
    apply_database_roles(connection, require_superuser=True)  # type: ignore[arg-type]


_SKIP = frozenset({"skip", "external"})


def _target_configured() -> bool:
    explicit = os.environ.get("AR_DB_SUPERUSER_URL", "").strip()
    host_set = os.environ.get("POSTGRES_HOST", "").strip()
    if explicit or host_set:
        return True
    host = urlsplit(os.environ.get("AR_DATABASE_URL", "")).hostname or ""
    return host in {"", "localhost", "127.0.0.1", "postgres"}


def main() -> None:
    """Console entry. Failures name the error type and never the password.

    ``AR_DB_RECONCILE=skip`` or ``external`` is the only successful no-op. A
    remote database without that setting fails.
    """
    mode = os.environ.get("AR_DB_RECONCILE", "run").strip().casefold() or "run"
    if mode in _SKIP:
        return
    if mode != "run":
        message = "AR_DB_RECONCILE must be run, skip, or external\n"
        sys.stderr.write(message)
        raise SystemExit(1)
    if not _target_configured():
        message = (
            "role reconciliation did not run: set POSTGRES_HOST or "
            "AR_DB_SUPERUSER_URL, or AR_DB_RECONCILE=skip for an external database\n"
        )
        sys.stderr.write(message)
        raise SystemExit(1)
    try:
        for role in APPLICATION_ROLES:
            role_password(role)
        _login()
        _run()
    except Exception as exc:  # noqa: BLE001
        detail = f"role reconciliation failed: {type(exc).__name__}: {_redact(str(exc))}\n"
        sys.stderr.write(detail)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

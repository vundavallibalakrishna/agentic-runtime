"""Reconcile application roles as the database superuser.

Existing volumes keep the previous chart's roles (``ar_owner`` is ``SUPERUSER``
and the other passwords are the role names). This command runs
``apply_database_roles`` on a superuser connection before migrations and the
app read the new secret. Running it again changes nothing.

The image superuser login is ``POSTGRES_USER`` / ``POSTGRES_PASSWORD``. An
upgrade from the previous chart sets those to a superuser that can still log
in (often ``postgres``, or ``ar_owner`` while it is still a superuser).
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import urlsplit

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from ar_common.database_roles import PASSWORD_ENV, assert_installed_database_secrets
from ar_domain.db.role_admin import apply_database_roles

_CONNECT_ARGS = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}


def superuser_url() -> str:
    """Build the superuser URL from the environment. The password stays out of argv."""
    explicit = os.environ.get("AR_DB_SUPERUSER_URL", "").strip()
    if explicit:
        return explicit
    user = os.environ.get("POSTGRES_USER", "").strip() or "postgres"
    password = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1").strip() or "127.0.0.1"
    database = os.environ.get("POSTGRES_DB", "agentic_runtime").strip() or "agentic_runtime"
    port = os.environ.get("POSTGRES_PORT", "").strip()
    port = port or os.environ.get("AR_PG_HOST_PORT", "").strip()
    if not user or not password:
        message = "POSTGRES_USER and POSTGRES_PASSWORD are required"
        raise RuntimeError(message)
    url = make_url("postgresql+asyncpg://")
    url = url.set(username=user, password=password, host=host, database=database)
    if port:
        url = url.set(port=int(port))
    return url.render_as_string(hide_password=False)


def _redact(message: str) -> str:
    redacted = message
    for name in (*PASSWORD_ENV.values(), "POSTGRES_PASSWORD"):
        secret = os.environ.get(name, "")
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    line = redacted.splitlines()[0] if redacted else ""
    return line[:300]


async def _run(url: str) -> None:
    engine = create_async_engine(url, connect_args=_CONNECT_ARGS)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_apply)
            await connection.commit()
    finally:
        await engine.dispose()


def _apply(connection: object) -> None:
    apply_database_roles(connection, require_superuser=True)  # type: ignore[arg-type]


def _local_database() -> bool:
    explicit = os.environ.get("AR_DB_SUPERUSER_URL", "").strip()
    host_set = os.environ.get("POSTGRES_HOST", "").strip()
    if explicit or host_set:
        return True
    host = urlsplit(os.environ.get("AR_DATABASE_URL", "")).hostname or ""
    return host in {"", "localhost", "127.0.0.1", "postgres"}


def main() -> None:
    """Console entry. Failures name the error type and never the password."""
    if not _local_database():
        return
    try:
        url = superuser_url()
        assert_installed_database_secrets(os.environ.get("AR_ENV", "dev"), url)
        asyncio.run(_run(url))
    except Exception as exc:  # noqa: BLE001
        detail = f"role reconciliation failed: {type(exc).__name__}: {_redact(str(exc))}\n"
        sys.stderr.write(detail)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

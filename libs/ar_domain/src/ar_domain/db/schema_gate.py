"""Apply the application schema once Postgres accepts the owner login.

The migrate Job and each database workload's init container run ``main``.
A session advisory lock serialises concurrent upgrades. ``/readyz`` calls
``assert_schema_current`` so a process does not serve an old schema.

Failures name the error type. The database URL and the role passwords are
removed from anything written to stderr.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from ar_common.database_roles import PASSWORD_ENV
from ar_domain.db.engine import owner_database_url

_LOCK_KEY = 872641
_DEFAULT_WAIT_S = 600.0


def head_revision() -> str:
    """The single Alembic head shipped in this image."""
    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    location = Path(__file__).resolve().parents[1] / "migrations"
    config = Config()
    config.set_main_option("script_location", str(location))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        message = "application schema does not have one Alembic head"
        raise RuntimeError(message)
    return heads[0]


def assert_schema_current_sync(url: str) -> None:
    """Raise when ``alembic_version`` is missing or is not the head revision."""
    expected = head_revision()
    engine = create_engine(_sync_url(url), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            query = text("SELECT version_num FROM alembic_version")
            rows = connection.execute(query).scalars().all()
    except Exception as exc:
        raise RuntimeError("application schema is not at the head revision") from exc
    finally:
        engine.dispose()
    if list(rows) != [expected]:
        message = "application schema is not at the head revision"
        raise RuntimeError(message)


async def assert_schema_current(url: str) -> None:
    """Readiness wrapper. The query runs off the event loop."""
    await asyncio.to_thread(assert_schema_current_sync, url)


def main() -> None:
    """Wait for the owner login, then upgrade to head under the advisory lock."""
    url = os.environ.get("AR_DATABASE_URL", "").strip()
    if not url:
        sys.stderr.write("schema gate: AR_DATABASE_URL is unset\n")
        raise SystemExit(1)
    wait_s = _wait_seconds()
    try:
        _wait_until_ready(url, wait_s)
        _upgrade_locked(url)
        assert_schema_current_sync(url)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"schema gate failed: {type(exc).__name__}: {_redact(str(exc))}\n")
        raise SystemExit(1) from None


def _wait_seconds() -> float:
    raw = os.environ.get("AR_SCHEMA_WAIT_S", "").strip() or str(_DEFAULT_WAIT_S)
    try:
        value = float(raw)
    except ValueError:
        sys.stderr.write("schema gate: AR_SCHEMA_WAIT_S is not a number\n")
        raise SystemExit(1) from None
    if value <= 0:
        sys.stderr.write("schema gate: AR_SCHEMA_WAIT_S must be positive\n")
        raise SystemExit(1)
    return value


def _wait_until_ready(url: str, wait_s: float) -> None:
    deadline = time.monotonic() + wait_s
    last = "database did not answer"
    while time.monotonic() < deadline:
        try:
            engine = create_engine(_sync_url(url), poolclass=NullPool)
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
            finally:
                engine.dispose()
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {_redact(str(exc))}"
            time.sleep(2)
            continue
        return
    sys.stderr.write(f"schema gate: database was not ready: {last[:300]}\n")
    raise SystemExit(1)


def _upgrade_locked(url: str) -> None:
    engine = create_engine(_sync_url(url), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _LOCK_KEY})
            connection.commit()
            try:
                _run_alembic()
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
                connection.commit()
    finally:
        engine.dispose()


def _run_alembic() -> None:
    ini = _alembic_ini()
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "-c", str(ini), "upgrade", "head"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = _redact(completed.stderr or completed.stdout)
        sys.stderr.write(f"schema upgrade failed: {detail[:400]}\n")
        raise SystemExit(1)


def _alembic_ini() -> Path:
    configured = os.environ.get("AR_ALEMBIC_INI", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path("/app/libs/ar_domain/alembic.ini"),
            Path(__file__).resolve().parents[3] / "alembic.ini",
        ]
    )
    for path in candidates:
        if path.is_file():
            return path
    sys.stderr.write("schema gate: alembic.ini was not found\n")
    raise SystemExit(1)


def _sync_url(url: str) -> str:
    owner = owner_database_url(url)
    if owner.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + owner.removeprefix("postgresql+asyncpg://")
    if owner.startswith("postgresql+psycopg://"):
        return owner
    if owner.startswith("postgresql://"):
        return "postgresql+psycopg://" + owner.removeprefix("postgresql://")
    return owner


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

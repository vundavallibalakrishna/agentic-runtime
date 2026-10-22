"""Alembic environment. Spec: docs/04-data/migrations.md."""

import asyncio
import os
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import ar_domain.agents.tables
import ar_domain.approvals.models
import ar_domain.audit.models
import ar_domain.conversations.tables
import ar_domain.events.models
import ar_domain.files.tables
import ar_domain.identity.models
import ar_domain.knowledge.tables
import ar_domain.models.tables
import ar_domain.policy.models
import ar_domain.sandboxes.tables
import ar_domain.secrets.models
import ar_domain.tools.tables
import ar_domain.usage.tables  # noqa: F401
from ar_common.host_ports import find_env_file, parse_env
from ar_domain.db import metadata
from ar_domain.db.engine import owner_database_url

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def _database_url() -> str:
    """Prefer the process environment, then the repo ``.env``.

    ``make migrate`` exports ``.env``. A direct ``uv run alembic`` call does not,
    and an empty ``AR_DATABASE_URL=`` must not win over the file.
    """
    raw = os.environ.get("AR_DATABASE_URL", "").strip()
    if raw:
        return raw
    env_file = find_env_file()
    if env_file is None:
        return ""
    return parse_env(env_file).get("AR_DATABASE_URL", "").strip()


database_url = _database_url()
if database_url:
    os.environ["AR_DATABASE_URL"] = database_url
    config.set_main_option("sqlalchemy.url", owner_database_url(database_url))


def run_migrations_offline() -> None:
    """Run migrations without a live connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations with an async engine."""
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

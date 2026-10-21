"""Alembic environment. Spec: docs/04-data/migrations.md."""

import asyncio
import os
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import ar_domain.agents.tables
import ar_domain.audit.models
import ar_domain.conversations.tables
import ar_domain.events.models
import ar_domain.files.tables
import ar_domain.identity.models
import ar_domain.models.tables
import ar_domain.secrets.models
import ar_domain.usage.tables  # noqa: F401
from ar_domain.db import metadata
from ar_domain.db.engine import owner_database_url

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata

database_url = os.environ.get("AR_DATABASE_URL", "")
if database_url:
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

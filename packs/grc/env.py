"""Pack Alembic environment. Version table `grc_alembic_version`. Core history is untouched."""

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ar_domain.db.engine import owner_database_url  # noqa: E402
from ar_pack_grc.models import PackBase  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = PackBase.metadata


def _database_url() -> str:
    raw = os.environ.get("AR_DATABASE_URL", "").strip()
    if raw:
        return raw
    from ar_common.host_ports import find_env_file, parse_env  # noqa: PLC0415

    env_file = find_env_file()
    if env_file is None:
        return ""
    return parse_env(env_file).get("AR_DATABASE_URL", "").strip()


database_url = _database_url()
if database_url:
    os.environ["AR_DATABASE_URL"] = database_url
    config.set_main_option("sqlalchemy.url", owner_database_url(database_url))


def include_object(
    obj: object,
    name: str,
    type_: str,
    reflected: bool,  # noqa: FBT001
    compare_to: object,
) -> bool:
    """Compare only schema `grc`. Core tables stay on the core Alembic head."""
    del name, reflected, compare_to
    if type_ == "table":
        return getattr(obj, "schema", None) == "grc"
    return True


def _configure(connection: Connection | None = None, *, url: str | None = None) -> None:
    kwargs: dict[str, object] = {
        "target_metadata": target_metadata,
        "include_schemas": True,
        "include_object": include_object,
        "version_table": "grc_alembic_version",
        "version_table_schema": "public",
        "compare_type": True,
        "compare_server_default": False,
    }
    if connection is not None:
        kwargs["connection"] = connection
    if url is not None:
        kwargs["url"] = url
        kwargs["literal_binds"] = True
        kwargs["dialect_opts"] = {"paramstyle": "named"}
    context.configure(**kwargs)


def run_migrations_offline() -> None:
    _configure(url=config.get_main_option("sqlalchemy.url"))
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    _configure(connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

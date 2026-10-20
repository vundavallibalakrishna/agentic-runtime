"""Upgrade the database and seed it. ``python -m ar_domain.migrations.run``."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from ar_domain.seed import apply


def main() -> None:
    """Run ``alembic upgrade head`` then the idempotent seed."""
    root = Path(__file__).resolve().parents[5]
    config = Config(str(root / "libs" / "ar_domain" / "alembic.ini"))
    command.upgrade(config, "head")
    asyncio.run(apply())


if __name__ == "__main__":
    main()

"""Upgrade the database. ``python -m ar_domain.migrations.run``.

It only migrates: seeding is a separate step (`scripts/seed_tenant.py` for a real tenant,
`scripts/seed.py` for the dev tenant). Migrating used to also run the dev seed, which put
the `dev` tenant, its people and the scripted provider into any database it touched
([F7](../../../../docs/testing/fresh-tenant-2026-11-06/report.md)).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    """Run ``alembic upgrade head``. It does not seed."""
    root = Path(__file__).resolve().parents[5]
    config = Config(str(root / "libs" / "ar_domain" / "alembic.ini"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()

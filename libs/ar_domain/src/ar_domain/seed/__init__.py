"""Apply the product seed on the owner connection."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from ar_domain.db.engine import get_engine, owner_database_url
from ar_domain.seed.plans import apply as apply_rows


async def apply() -> None:
    """Seed plans, roles and the dev tenant. Migrations must already be at head."""
    engine = get_engine(owner_database_url())
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply_rows(session)


def main() -> None:
    """Console entry used by ``scripts/seed.py``."""
    asyncio.run(apply())

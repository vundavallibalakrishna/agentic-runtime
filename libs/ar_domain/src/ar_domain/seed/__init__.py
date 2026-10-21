"""Apply the product seed on the owner connection."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from ar_domain.db.engine import get_engine, owner_database_url
from ar_domain.identity.seed import user_id_for_email
from ar_domain.seed.m2 import apply as apply_m2
from ar_domain.seed.plans import apply as apply_rows


async def apply() -> None:
    """Seed plans, roles, the dev tenant, fake-llm and the assistant."""
    engine = get_engine(owner_database_url())
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        tenant_id = await apply_rows(session)
        admin_id = await user_id_for_email(session, tenant_id, "admin@dev.local")
        await apply_m2(session, tenant_id, admin_id)


def main() -> None:
    """Console entry used by ``scripts/seed.py``."""
    asyncio.run(apply())

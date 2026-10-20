"""Single-tenant bootstrap. ``python -m ar_domain.bootstrap``.

Spec: docs/00-overview/deployment-modes.md, docs/03-specs/02-identity-tenancy.md §4.
"""

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession

from ar_domain.db.engine import get_engine, owner_database_url
from ar_domain.identity.seed import ensure_admin
from ar_domain.seed import apply


async def bootstrap(
    *,
    slug: str | None = None,
    name: str | None = None,
    admin_email: str | None = None,
) -> str:
    """Ensure a tenant and its admin user exist. Returns the tenant slug."""
    tenant_slug = slug or os.environ.get("AR_BOOTSTRAP_TENANT_SLUG", "dev")
    tenant_name = name or os.environ.get("AR_BOOTSTRAP_TENANT_NAME", "Dev")
    email = admin_email or os.environ.get("AR_BOOTSTRAP_ADMIN_EMAIL", "admin@dev.local")
    await apply()
    engine = get_engine(owner_database_url())
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        return await ensure_admin(session, slug=tenant_slug, name=tenant_name, email=email)


def main() -> None:
    """Console entry."""
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()

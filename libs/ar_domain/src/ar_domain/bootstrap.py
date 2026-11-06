"""Single-tenant bootstrap. ``python -m ar_domain.bootstrap``.

Creates the plans and system roles, one tenant and its first tenant admin. It creates no
model provider, no agent and no example data: the admin adds those in the product.

Spec: docs/00-overview/deployment-modes.md, docs/03-specs/02-identity-tenancy.md §4.
"""

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession

from ar_domain.db.engine import get_engine, owner_database_url
from ar_domain.db.registry import import_models
from ar_domain.identity.seed import apply_catalogue, ensure_admin


async def bootstrap(
    *,
    slug: str | None = None,
    name: str | None = None,
    admin_email: str | None = None,
    admin_name: str | None = None,
) -> str:
    """Ensure a tenant and its admin user exist. Returns the tenant slug."""
    tenant_slug = slug or os.environ.get("AR_BOOTSTRAP_TENANT_SLUG") or "default"
    tenant_name = name or os.environ.get("AR_BOOTSTRAP_TENANT_NAME") or "Default"
    email = admin_email or os.environ.get("AR_BOOTSTRAP_ADMIN_EMAIL") or ""
    if "@" not in email:
        raise SystemExit("AR_BOOTSTRAP_ADMIN_EMAIL is required: the address of the first admin")
    import_models()
    engine = get_engine(owner_database_url())
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply_catalogue(session)
        return await ensure_admin(
            session, slug=tenant_slug, name=tenant_name, email=email, display_name=admin_name
        )


def main() -> None:
    """Console entry."""
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()

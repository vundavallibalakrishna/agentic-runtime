"""Single-tenant bootstrap. ``python -m ar_domain.bootstrap``.

Creates the plans and system roles, one tenant, its first tenant admin, and the two
agents every tenant has (the assistant and the builder), owned by that admin. It creates
no model provider and no example data: the admin adds those in the product.

Spec: docs/00-overview/deployment-modes.md, docs/03-specs/02-identity-tenancy.md §4.
"""

import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession

from ar_domain.db.engine import app_database_url, get_engine, owner_database_url
from ar_domain.db.registry import import_models
from ar_domain.identity.seed import apply_catalogue, ensure_admin


async def bootstrap(
    *,
    slug: str | None = None,
    name: str | None = None,
    admin_email: str | None = None,
    admin_name: str | None = None,
    admin_password: str | None = None,
) -> str:
    """Ensure a tenant and its admin user exist. Returns the tenant slug.

    When ``admin_password`` is given, the admin can sign in with it: sign-in is in-app and
    the password is stored as an argon2id hash on the user row.
    """
    tenant_slug = slug or os.environ.get("AR_BOOTSTRAP_TENANT_SLUG") or "default"
    tenant_name = name or os.environ.get("AR_BOOTSTRAP_TENANT_NAME") or "Default"
    email = admin_email or os.environ.get("AR_BOOTSTRAP_ADMIN_EMAIL") or ""
    if "@" not in email:
        raise SystemExit("AR_BOOTSTRAP_ADMIN_EMAIL is required: the address of the first admin")
    import_models()
    engine = get_engine(owner_database_url())
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply_catalogue(session)
        await ensure_admin(
            session,
            slug=tenant_slug,
            name=tenant_name,
            email=email,
            display_name=admin_name,
            password=admin_password,
        )
    await provision_defaults(tenant_slug, email)
    return tenant_slug


async def provision_defaults(tenant_slug: str, owner_email: str) -> None:
    """Write the tenant's default agents and the tool catalogue to the database.

    This goes through the same store a process uses, so the rows are the ones a process
    then loads. The owner is a real user of the tenant. Running it again changes nothing.
    """
    from ar_domain.agents.service import AgentLifecycle  # noqa: PLC0415
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.bind import bind_store  # noqa: PLC0415
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415

    store = ChatService(fake_models_allowed=False)
    binding = await bind_store(store, app_database_url(), tenant_slug=tenant_slug)
    if binding is None:
        raise SystemExit("The database stopped answering before the default agents were made.")
    try:
        owner = binding.users[owner_email.strip().lower()]
        AgentLifecycle(store).ensure_builtins(binding.tenant_id, owner)
        await flush_store(store)
    finally:
        if store.durable_engine is not None:
            await store.durable_engine.dispose()


def main() -> None:
    """Console entry."""
    asyncio.run(bootstrap())


if __name__ == "__main__":
    main()

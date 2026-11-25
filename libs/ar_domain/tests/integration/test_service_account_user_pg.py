"""A service account on Postgres: it has a user of its own, so what it creates has an owner.

Before this, a file a service-account key uploaded failed on the owner's foreign key.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.seed import apply
from ar_domain.identity.service import IdentityService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)
    url = url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def test_a_service_account_has_a_user_that_can_own_a_file_and_is_not_a_person(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
        tenant_id = (
            await session.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).scalar_one()
        admin_id = (
            await session.execute(
                text("SELECT id FROM users WHERE tenant_id = :t ORDER BY created_at LIMIT 1"),
                {"t": tenant_id},
            )
        ).scalar_one()
    ctx = TenantContext.from_principal(
        Principal(kind="user", id=str(admin_id), tenant_id=tenant_id, permissions=PERMISSION_KEYS),
        "req-service-user",
    )
    name = f"bot-{uuid.uuid4().hex[:8]}"
    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        account = await service.create_service_account(
            name=name, description="", allow_on_behalf_of=False
        )
        account_id = account.id
        # The id is known before the row is saved, so the reply can name it.
        assert isinstance(account_id, uuid.UUID)
    file_id = uuid.uuid4()
    try:
        async with tenant_session(ctx, engine=engine) as session:
            store = IdentityRepository(session, ctx)
            owner = await store.get_user(account_id)
            assert owner is not None
            assert (owner.kind, owner.status, owner.display_name) == ("service", "active", name)
            assert owner.password_hash is None
            # It is not one of the people of the workspace, by list or by address.
            assert account_id not in [
                row.id for row in await store.list_users(status=None, query=None)
            ]
            assert await store.get_user_by_email(owner.email) is None
            # What failed before: a row owned by the account.
            await session.execute(
                text(
                    "INSERT INTO files (id, tenant_id, owner_user_id, kind, name, mime_type, "
                    "size_bytes, sha256, object_key, status) VALUES (:id, :t, :owner, 'upload', "
                    "'a.txt', 'text/plain', 1, :sha, :key, 'ready')"
                ),
                {
                    "id": file_id,
                    "t": tenant_id,
                    "owner": account_id,
                    "sha": uuid.uuid4().hex,
                    "key": f"tenants/{tenant_id}/upload/{file_id}",
                },
            )
    finally:
        async with AsyncSession(engine) as session, session.begin():
            for statement in (
                "DELETE FROM files WHERE id = :file",
                "DELETE FROM service_accounts WHERE id = :account",
                "DELETE FROM users WHERE id = :account",
            ):
                await session.execute(text(statement), {"file": file_id, "account": account_id})
        await engine.dispose()

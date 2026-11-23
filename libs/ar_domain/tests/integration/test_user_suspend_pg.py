"""Suspending a person on Postgres: the row, the audit trail and what every request reads.

Suspended in one transaction and read in another, as different replicas would. The store a
request is served from reloads people's status from the ``users`` table, which is what
shuts a suspended person's open sessions out.
"""

import os
import subprocess
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.errors import ArError
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.durable.hydrate import _people
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.seed import apply
from ar_domain.identity.service import IdentityService

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def _status_a_request_reads(engine: object, tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    store = SimpleNamespace(user_statuses={}, display_names={}, user_emails={}, user_roles={})
    async with AsyncSession(engine) as session:  # type: ignore[arg-type]
        await _people(session, store, tenant_id)
    return str(store.user_statuses[user_id])


async def _audited(engine: object, action: str, user_id: uuid.UUID) -> int:
    async with engine.connect() as connection:  # type: ignore[attr-defined]
        found = await connection.execute(
            text("SELECT count(*) FROM audit_events WHERE action = :action AND target_id = :id"),
            {"action": action, "id": str(user_id)},
        )
        return int(found.scalar_one())


async def test_a_suspension_is_saved_audited_and_read_by_the_next_request(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
        tenant_id = (
            await session.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).scalar_one()
        people = dict(
            (
                await session.execute(
                    text("SELECT email, id FROM users WHERE tenant_id = :t"), {"t": tenant_id}
                )
            ).all()
        )
    admin_id, member_id = people["admin@dev.local"], people["member@dev.local"]
    principal = Principal(kind="user", id=str(admin_id), tenant_id=tenant_id)
    ctx = TenantContext(
        tenant_id=tenant_id, user_id=admin_id, principal=principal, request_id="test"
    )
    before = await _audited(engine, "user.suspended", member_id)

    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        await service.patch_user(member_id, status="suspended", attributes=None)
    assert await _status_a_request_reads(engine, tenant_id, member_id) == "suspended"
    assert await _audited(engine, "user.suspended", member_id) == before + 1

    # Suspending someone who is already suspended is not a second event.
    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        await service.patch_user(member_id, status="suspended", attributes=None)
    assert await _audited(engine, "user.suspended", member_id) == before + 1

    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        with pytest.raises(ArError, match="your own account"):
            await service.patch_user(admin_id, status="suspended", attributes=None)
    assert await _status_a_request_reads(engine, tenant_id, admin_id) == "active"

    reactivated = await _audited(engine, "user.reactivated", member_id)
    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        await service.patch_user(member_id, status="active", attributes=None)
    assert await _status_a_request_reads(engine, tenant_id, member_id) == "active"
    assert await _audited(engine, "user.reactivated", member_id) == reactivated + 1
    await engine.dispose()

"""Accepting an invitation on Postgres: the person, their role and the audit row are saved.

Invited in one transaction and accepted in another, as different replicas would. Another
tenant's context cannot use the token.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.errors import ArError
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.identity.passwords import verify_password
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


def _login_context(tenant_id: uuid.UUID) -> TenantContext:
    principal = Principal(kind="system", id="login", tenant_id=tenant_id)
    return TenantContext.from_principal(principal, "test")


async def test_an_invitation_made_in_one_transaction_is_accepted_in_another(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
        tenant_id = (
            await session.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).scalar_one()
    ctx = _login_context(tenant_id)
    email = f"invited-{uuid.uuid4().hex[:8]}@example.test"

    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        [(_row, token)] = await service.invite([email], ["member"])

    other = _login_context(uuid.uuid4())
    async with tenant_session(other, engine=engine) as session:
        await session.execute(text("SET LOCAL ROLE ar_app"))
        with pytest.raises(ArError, match="not valid"):
            await IdentityService(IdentityRepository(session, other)).accept_invitation(
                token, "Someone", "a-good-password"
            )

    async with tenant_session(ctx, engine=engine) as session:
        service = IdentityService(IdentityRepository(session, ctx))
        user = await service.accept_invitation(token, "Invited Person", "a-good-password")
        user_id = user.id

    async with engine.connect() as connection:
        saved = (
            await connection.execute(
                text("SELECT email, display_name, status, password_hash FROM users WHERE id = :id"),
                {"id": user_id},
            )
        ).one()
        roles = (
            await connection.execute(
                text(
                    "SELECT r.key FROM role_assignments a JOIN roles r ON r.id = a.role_id "
                    "WHERE a.principal_id = :id AND a.principal_type = 'user'"
                ),
                {"id": user_id},
            )
        ).scalars()
        accepted = (
            await connection.execute(
                text("SELECT accepted_at FROM invitations WHERE email = :email"), {"email": email}
            )
        ).scalar_one()
        audited = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action = 'user.provisioned' "
                    "AND target_id = :id"
                ),
                {"id": str(user_id)},
            )
        ).scalar_one()
    assert (saved.email, saved.display_name, saved.status) == (email, "Invited Person", "active")
    assert verify_password(saved.password_hash, "a-good-password")
    assert list(roles) == ["member"]
    assert accepted is not None
    assert audited == 1

    async with tenant_session(ctx, engine=engine) as session:
        with pytest.raises(ArError, match="already been used"):
            await IdentityService(IdentityRepository(session, ctx)).accept_invitation(
                token, "Again", "another-password"
            )
    await engine.dispose()

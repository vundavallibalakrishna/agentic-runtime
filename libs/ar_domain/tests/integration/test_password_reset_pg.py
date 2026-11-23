"""A password reset on Postgres: asked in one transaction, completed in another.

The reset row is in ``password_resets`` and the new password is on the user's row, so the
two steps can be served by different replicas. Another tenant sees neither.
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
from ar_domain.identity.passwords import hash_password, verify_password
from ar_domain.identity.recovery import _hash, confirm_reset, request_reset
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.seed import apply

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
    """The context sign-in and reset open the tenant's identity rows with."""
    principal = Principal(kind="system", id="login", tenant_id=tenant_id)
    return TenantContext.from_principal(principal, "test")


async def test_a_reset_asked_in_one_transaction_is_completed_in_another(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
        tenant_id = (
            await session.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).scalar_one()
        email = f"reset-{uuid.uuid4().hex[:8]}@example.test"
        user_id = uuid.uuid4()
        await session.execute(
            text(
                "INSERT INTO users (id, tenant_id, idp_subject, email, display_name, status, "
                "password_hash) VALUES (:id, :tenant, :subject, :email, 'Reset Person', "
                "'active', :hash)"
            ),
            {
                "id": user_id,
                "tenant": tenant_id,
                "subject": email,
                "email": email,
                "hash": hash_password("the-old-password"),
            },
        )
    ctx = _login_context(tenant_id)

    async with tenant_session(ctx, engine=engine) as session:
        token = await request_reset(IdentityRepository(session, ctx), email)
    assert token

    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT token_hash, used_at FROM password_resets WHERE user_id = :id"),
                {"id": user_id},
            )
        ).all()
    assert [(row.token_hash, row.used_at) for row in rows] == [(_hash(token), None)]

    # Another tenant's context finds no such reset.
    other = _login_context(uuid.uuid4())
    async with tenant_session(other, engine=engine) as session:
        await session.execute(text("SET LOCAL ROLE ar_app"))
        with pytest.raises(ArError, match="not valid"):
            await confirm_reset(IdentityRepository(session, other), token, "a-new-password")

    async with tenant_session(ctx, engine=engine) as session:
        changed = await confirm_reset(IdentityRepository(session, ctx), token, "a-new-password")
    assert changed.id == user_id

    async with engine.connect() as connection:
        saved = (
            await connection.execute(
                text("SELECT password_hash, password_set_at FROM users WHERE id = :id"),
                {"id": user_id},
            )
        ).one()
        spent = (
            await connection.execute(
                text("SELECT used_at FROM password_resets WHERE user_id = :id"), {"id": user_id}
            )
        ).scalar_one()
        audited = (
            await connection.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action = 'auth.password_reset' "
                    "AND target_id = :id"
                ),
                {"id": str(user_id)},
            )
        ).scalar_one()
    assert verify_password(saved.password_hash, "a-new-password")
    assert not verify_password(saved.password_hash, "the-old-password")
    assert saved.password_set_at is not None
    assert spent is not None
    assert audited == 1

    async with tenant_session(ctx, engine=engine) as session:
        with pytest.raises(ArError, match="not valid"):
            await confirm_reset(IdentityRepository(session, ctx), token, "yet-another-one")
    await engine.dispose()

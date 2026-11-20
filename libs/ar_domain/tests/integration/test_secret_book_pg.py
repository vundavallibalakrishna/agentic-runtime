"""A secret saved through the product is stored, audited, and found by a tool by its name.

A tool that takes a secret name used to look in a copy kept in one process's memory. The
copy never reached the database, so on a database-backed install the tool found nothing.
"""

import base64
import os
import subprocess
import uuid

import orjson
import pytest
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.settings import get_settings, set_settings
from ar_domain.chat.service import ChatService
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.durable.bind import bind_store
from ar_domain.durable.hydrate import hydrate_tenant
from ar_domain.identity.seed import apply
from ar_domain.secrets.book import SecretBook
from ar_domain.tools.named_secrets import read_named_secret

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


@pytest.fixture
def keyring() -> object:
    """An install whose database holds secret values, with one key in its ring."""
    before = get_settings()
    ring = orjson.dumps({"k1": base64.b64encode(b"k" * 32).decode()}).decode()
    set_settings(
        before.model_copy(
            update={
                "secrets_backend": "db_encrypted",
                "db_encryption_keys": SecretStr(ring),
                "db_encryption_active_key": "k1",
            }
        )
    )
    yield None
    set_settings(before)


def _ctx(tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> TenantContext:
    principal = Principal(
        kind="user" if user_id else "system",
        id=str(user_id or "system"),
        tenant_id=tenant_id,
        permissions=frozenset({"secrets:use", "secrets:manage"}),
    )
    return TenantContext(
        tenant_id=tenant_id, user_id=user_id, principal=principal, request_id="req-test"
    )


async def test_a_saved_secret_is_audited_and_a_tool_finds_it_by_name(
    database_url: str, keyring: object
) -> None:
    del keyring
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    worker = ChatService()
    assert await bind_store(worker, database_url, tenant_slug="dev") is not None
    tenant = worker.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(worker.tenant_binding.users.values()))  # type: ignore[union-attr]
    ctx = _ctx(tenant, admin)
    name = f"vendor-{uuid.uuid4().hex[:8]}"

    async with tenant_session(ctx, engine=engine) as session:
        book = SecretBook(session, ctx)
        made = await book.create(name, "bearer_token", "first-value", "the vendor's token")
        assert made.version == 1
        with pytest.raises(ValidationFailedError):
            await book.create("other", "not-a-kind", "x", "")
        with pytest.raises(ValidationFailedError):
            await book.create("  ", "generic", "x", "")
    async with tenant_session(ctx, engine=engine) as session:
        with pytest.raises(ConflictError):
            await SecretBook(session, ctx).create(name, "generic", "again", "")

    # A worker that was already running finds it by name once it has read the tenant again.
    assert read_named_secret(worker, tenant, name) is None
    await hydrate_tenant(worker, engine, tenant)
    assert read_named_secret(worker, tenant, name) == "first-value"
    assert read_named_secret(worker, uuid.uuid4(), name) is None
    assert read_named_secret(worker, tenant, "no-such-secret") is None
    # The loaded row holds the sealed value, never the plaintext.
    assert "first-value" not in str(worker.stored_secrets)

    async with tenant_session(ctx, engine=engine) as session:
        book = SecretBook(session, ctx)
        assert name in [row.name for row in await book.list()]
        assert (await book.describe(made.id, "rotated yearly")).description == "rotated yearly"
        assert (await book.rotate(made.id, "second-value")).version == 2
    await hydrate_tenant(worker, engine, tenant)
    assert read_named_secret(worker, tenant, name) == "second-value"

    # Another tenant can neither read the row nor open the value.
    other = uuid.uuid4()
    async with AsyncSession(engine) as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO tenants (id, slug, name, plan_id) "
                "SELECT :id, :slug, 'Other', plan_id FROM tenants WHERE id = :mine"
            ),
            {"id": other, "slug": f"other-{other.hex[:8]}", "mine": tenant},
        )
    stranger = _ctx(other, None)
    async with tenant_session(stranger, engine=engine) as session:
        theirs = SecretBook(session, stranger)
        assert await theirs.list() == []
        with pytest.raises(NotFoundError):
            await theirs.get(made.id)
        with pytest.raises(NotFoundError):
            await theirs.rotate(made.id, "stolen")
    elsewhere = ChatService()
    await hydrate_tenant(elsewhere, engine, other)
    assert read_named_secret(elsewhere, other, name) is None

    async with tenant_session(ctx, engine=engine) as session:
        await SecretBook(session, ctx).delete(made.id)
    await hydrate_tenant(worker, engine, tenant)
    assert read_named_secret(worker, tenant, name) is None

    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT action, detail::text AS detail FROM audit_events "
                    "WHERE tenant_id = :t AND target_id = :id ORDER BY tenant_seq"
                ),
                {"t": tenant, "id": str(made.id)},
            )
        ).all()
        left = await connection.scalar(
            text("SELECT count(*) FROM encrypted_secrets WHERE tenant_id = :t"), {"t": tenant}
        )
    assert [row.action for row in rows] == [
        "secret.created",
        "secret.updated",
        "secret.rotated",
        "secret.deleted",
    ]
    assert all("value" not in row.detail for row in rows)
    assert left == 0
    await engine.dispose()

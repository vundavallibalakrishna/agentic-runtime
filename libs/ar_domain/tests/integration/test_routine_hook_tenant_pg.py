"""A call to a routine's webhook is matched to the tenant that owns the address.

On a database-backed install the call was answered "not found": it carries no sign-in, so
no tenant's routines were loaded for it.
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

from ar_common.settings import get_settings, set_settings
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.readmodel.model import RepositoryReadModel
from ar_domain.routines.book import RoutineBook

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
    """An install whose database holds secret values: a routine's webhook secret is one."""
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


@pytest.mark.usefixtures("keyring")
async def test_a_webhook_address_names_its_tenant_and_an_unknown_one_names_none(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    tenant = store.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(store.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")
    async with engine.connect() as connection:
        before = list(
            (
                await connection.scalars(
                    text("SELECT id FROM encrypted_secrets WHERE tenant_id = :t"), {"t": tenant}
                )
            ).all()
        )
        refs = list(
            (
                await connection.scalars(
                    text("SELECT id FROM secret_refs WHERE tenant_id = :t"), {"t": tenant}
                )
            ).all()
        )
    slug = f"hooked-{uuid.uuid4().hex[:8]}"
    agent = AgentLifecycle(store).create(actor, slug=slug, name="Hooked", description="")
    made = RoutineBook(store).create(
        actor,
        {
            "name": f"hook {slug}",
            "agent_id": uuid.UUID(str(agent["id"])),
            "instructions": "Say hello.",
            "trigger": {"type": "webhook"},
        },
    )
    address = str(made["webhook"]["webhook_url"])  # type: ignore[index]
    token = address.rsplit("/", 1)[-1]
    await flush_store(store)
    model = RepositoryReadModel(database_url=database_url)
    try:
        assert await model.tenant_of_hook(token) == tenant
        assert await model.tenant_of_hook(f"{token}-not") is None
        assert await model.tenant_of_hook("") is None
    finally:
        # The database is shared with the other tests of this run: leave it as it was found.
        # The routine's webhook secret is a stored secret of its own, so it goes too.
        async with AsyncSession(engine) as session, session.begin():
            for statement in (
                "DELETE FROM encrypted_secrets WHERE tenant_id = :tenant AND id NOT IN "
                "(SELECT unnest(CAST(:before AS uuid[])))",
                "DELETE FROM routines WHERE id = :routine",
                "DELETE FROM secret_refs WHERE tenant_id = :tenant AND id NOT IN "
                "(SELECT unnest(CAST(:refs AS uuid[])))",
                "UPDATE agents SET draft_version_id = NULL, published_version_id = NULL "
                "WHERE id = :agent",
                "DELETE FROM agent_versions WHERE agent_id = :agent",
                "DELETE FROM agents WHERE id = :agent",
            ):
                await session.execute(
                    text(statement),
                    {
                        "tenant": tenant,
                        "before": before,
                        "refs": refs,
                        "routine": uuid.UUID(str(made["id"])),
                        "agent": uuid.UUID(str(agent["id"])),
                    },
                )
        if model.engine is not None:
            await model.engine.dispose()
        await engine.dispose()

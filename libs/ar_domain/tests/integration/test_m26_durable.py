"""Connector installs, OAuth state, grants and named secrets survive a new process."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.connectors.book import ConnectorBook
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.tools.credentials import CredentialBook
from ar_domain.tools.named_secrets import read_named_secret, write_named_secret

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)


def _alembic(url: str) -> None:
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url)
    return url


async def test_connector_records_survive_a_new_process(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    store = ChatService(tenant_seed=False)
    binding = await bind_store(store, database_url)
    assert binding is not None
    actor = Actor(
        binding.tenant_id,
        binding.users["admin@dev.local"],
        PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
    )
    ConnectorBook(store).install(actor, "github", {"connection_name": "public-read"})
    write_named_secret(store, binding.tenant_id, "vendor", "kept-secret")
    provider = CredentialBook(store).create_provider(
        actor,
        {
            "slug": "m26-oauth",
            "name": "M26",
            "kind": "oauth2",
            "authorize_url": "https://example.com/authorize",
            "token_url": "memory://oauth",
            "client_id": "m26",
            "default_scopes": ["read"],
        },
    )
    CredentialBook(store).start(actor, uuid.UUID(str(provider["id"])))
    await flush_store(store)
    await engine.dispose()

    restarted = ChatService(tenant_seed=False)
    again = await bind_store(restarted, database_url)
    assert again is not None
    seen = ConnectorBook(restarted).get(actor, "github")
    assert seen["installed"] is True
    assert read_named_secret(restarted, binding.tenant_id, "vendor") == "kept-secret"
    states = [
        row
        for row in restarted.oauth_states.values()
        if isinstance(row, dict) and row.get("tenant_id") == binding.tenant_id
    ]
    assert states
    assert states[0].get("verifier")
    # The sign-in that one process started is finished by the next, and the grant it
    # produces is there for a third.
    state = next(
        key
        for key, row in restarted.oauth_states.items()
        if isinstance(row, dict) and row.get("tenant_id") == binding.tenant_id
    )
    await CredentialBook(restarted).callback("code-from-the-provider", str(state))
    await flush_store(restarted)
    third = ChatService(tenant_seed=False)
    assert await bind_store(third, database_url) is not None
    grants = [
        row
        for row in third.credential_grants.values()
        if row.get("tenant_id") == binding.tenant_id and row.get("provider_id")
    ]
    assert grants
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        installs = await connection.scalar(
            text("SELECT count(*) FROM connector_installs WHERE slug = 'github'")
        )
        secrets = await connection.scalar(
            text("SELECT count(*) FROM named_secrets WHERE name = 'vendor'")
        )
    await engine.dispose()
    assert installs == 1
    assert secrets == 1

"""GRC rows survive a database save and a reload, with their identifier types."""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from grc_pack import enable
from grc_pack.book import CatalogueBook
from grc_pack.tools import PACK_PERMISSIONS

pytestmark = pytest.mark.integration

_CSV = "key,title,statement\nD1,Door,The door stays locked after hours.\n"


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


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


async def test_a_catalogue_reloads_with_uuid_identifiers(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    store = ChatService()
    binding = await bind_store(store, database_url, tenant_slug="dev")
    assert binding is not None
    admin = binding.users["admin@dev.local"]
    enable(store, binding.tenant_id, owner=admin)
    actor = Actor(
        binding.tenant_id,
        admin,
        PERMISSION_KEYS | frozenset(PACK_PERMISSIONS) | frozenset({"evidence:read"}),
        roles=frozenset({"tenant_admin"}),
    )
    imported = CatalogueBook(store).import_csv(actor, "House rules", _CSV)
    catalogue_id = uuid.UUID(str(imported["id"]))
    await flush_store(store)
    fresh = ChatService()
    again = await bind_store(fresh, database_url, tenant_slug="dev")
    assert again is not None
    items = CatalogueBook(fresh).items(actor, catalogue_id)
    assert items
    assert items[0]["catalogue_id"] == catalogue_id
    await engine.dispose()

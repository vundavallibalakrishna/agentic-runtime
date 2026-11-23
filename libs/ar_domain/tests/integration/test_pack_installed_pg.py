"""An installed pack is remembered: another process lists it, upgrades it and removes it."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.errors import ArError, ErrorCode
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
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


async def _bound(database_url: str) -> tuple[ChatService, Actor]:
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    tenant = store.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(store.tenant_binding.users.values()))  # type: ignore[union-attr]
    return store, Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")


def _slug(pack_id: str) -> str:
    return pack_id.replace("_", "-") + "-agent"


def _manifest(pack_id: str, version: str, instructions: str) -> dict[str, object]:
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": pack_id, "version": version, "name": "Kept"},
        "spec": {
            "resources": [
                {
                    "kind": "Agent",
                    "metadata": {"slug": _slug(pack_id), "name": "Kept agent"},
                    "spec": {"instructions": instructions},
                }
            ]
        },
    }


async def test_another_process_sees_upgrades_and_removes_an_installed_pack(
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    pack_id = f"kept_{uuid.uuid4().hex[:8]}"
    first, actor = await _bound(database_url)
    installed = PackService(first).install(
        actor, _manifest(pack_id, "1.0.0", "Say hello."), signature=None, key_id=None
    )
    assert installed["status"] == "installed"
    await flush_store(first)

    second, actor = await _bound(database_url)
    packs = PackService(second)
    listed = [row for row in packs.list_packs(actor) if row["pack_id"] == pack_id]
    assert [(row["version"], row["status"]) for row in listed] == [("1.0.0", "installed")]
    shown = packs.get(actor, pack_id)
    assert [(row["kind"], row["slug"]) for row in shown["resources"]] == [  # type: ignore[union-attr]
        ("Agent", _slug(pack_id))
    ]
    packs.upgrade(
        actor,
        pack_id,
        _manifest(pack_id, "1.1.0", "Say hello twice."),
        signature=None,
        key_id=None,
        accept_conflicts=False,
    )
    await flush_store(second)

    third, actor = await _bound(database_url)
    assert PackService(third).get(actor, pack_id)["version"] == "1.1.0"
    PackService(third).uninstall(actor, pack_id, drop_schema=False)
    await flush_store(third)

    fourth, actor = await _bound(database_url)
    with pytest.raises(ArError) as gone:
        PackService(fourth).get(actor, pack_id)
    assert gone.value.code is ErrorCode.NOT_FOUND

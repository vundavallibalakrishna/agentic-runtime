"""A tool imported from an API description keeps its name: another process can call it."""

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
from ar_domain.tools.imports import ToolImporter

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


def _document() -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Scores", "version": "1.0"},
        "servers": [{"url": "https://scores.example.test/v1"}],
        "paths": {
            "/score": {
                "get": {
                    "operationId": "look_up_score",
                    "summary": "The score of one item.",
                    "parameters": [
                        {
                            "name": "item",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "The score."}},
                }
            }
        },
    }


def _versions(store: ChatService, slug: str) -> list[dict[str, object]]:
    server = next(row for row in store.tool_servers.values() if row.get("slug") == slug)
    tools = {
        key for key, row in store.tool_defs.items() if row.get("tool_server_id") == server["id"]
    }
    return [row for row in store.tool_versions.values() if row.get("tool_id") in tools]


async def test_an_imported_tool_is_named_in_another_process(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    slug = f"scores_{uuid.uuid4().hex[:8]}"
    first, actor = await _bound(database_url)
    ToolImporter(first).import_openapi(actor, {"slug": slug, "document": _document()})
    [made] = _versions(first, slug)
    assert made["qualified_name"] == f"{slug}.look_up_score"
    await flush_store(first)

    second, _actor = await _bound(database_url)
    [seen] = _versions(second, slug)
    # The name an agent's tool list is matched against, and the one a run calls it by.
    assert seen["name"] == "look_up_score"
    assert seen["qualified_name"] == f"{slug}.look_up_score"
    # It was sent for review, which needs every risk class confirmed.
    assert seen["risk_confirmed"] is True

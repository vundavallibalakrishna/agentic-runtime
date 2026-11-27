"""Revision 0063 moves a routine off the old default budget and leaves a set one alone."""

import importlib
import os
import subprocess
import uuid

import orjson
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.routines.book import RoutineBook

pytestmark = pytest.mark.integration

_REVISION = importlib.import_module(
    "ar_domain.migrations.versions.20261123_0063_routine_budget_default"
)
_OLD = {
    "max_steps": 8,
    "max_tokens": 8000,
    "max_cost_micros": 0,
    "max_wall_clock_s": 300,
    "max_tool_calls": 4,
    "max_parallel_tool_calls": 1,
}


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


async def _budgets(engine: object, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    async with engine.connect() as connection:  # type: ignore[attr-defined]
        rows = await connection.execute(
            text("SELECT id, budget FROM routines WHERE id = ANY(:ids)"), {"ids": ids}
        )
        return {row.id: row.budget for row in rows}


async def test_only_the_old_default_is_replaced(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    tenant = store.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(store.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")
    agent = store.ensure_assistant(tenant, admin)
    book = RoutineBook(store)
    tag = uuid.uuid4().hex[:8]

    def made(name: str, budget: dict[str, int]) -> uuid.UUID:
        row = book.create(
            actor,
            {
                "name": f"{name} {tag}",
                "agent_id": uuid.UUID(str(agent["id"])),
                "instructions": "Say hello.",
                "trigger": {"type": "manual"},
                "budget": budget,
            },
        )
        return uuid.UUID(str(row["id"]))

    custom = {**_OLD, "max_tool_calls": 6}
    old_id, set_id = made("old default", _OLD), made("set by a person", custom)
    await flush_store(store)
    assert (await _budgets(engine, [old_id]))[old_id] == _OLD

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE routines SET budget = CAST(:new AS jsonb) "
                "WHERE budget = CAST(:old AS jsonb) OR budget = '{}'::jsonb"
            ),
            {"new": _REVISION._NEW, "old": _REVISION._OLD},
        )
    after = await _budgets(engine, [old_id, set_id])
    # The revision keeps the budget it wrote. Later changes to the live default do not
    # rewrite a migration that has already run.
    assert after[old_id] == orjson.loads(_REVISION._NEW)
    assert after[set_id] == custom
    await engine.dispose()

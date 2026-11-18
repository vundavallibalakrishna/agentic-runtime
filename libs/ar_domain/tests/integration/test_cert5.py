"""Postgres regressions from live certification run 5."""

from __future__ import annotations

import os
import subprocess
import uuid

import asyncpg
import orjson
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.json_api import camelize, dumps
from ar_domain.chat.service import demo_id
from ar_domain.durable.evals import save_eval_rows
from ar_domain.identity.seed import apply
from ar_testing.containers import to_libpq_url

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    return postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)


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


async def test_public_json_encodes_a_real_asyncpg_row(postgres_url: str) -> None:
    connection = await asyncpg.connect(to_libpq_url(postgres_url))
    try:
        row = await connection.fetchrow(
            "SELECT gen_random_uuid() AS id, now() AS at, 12.50::numeric AS amount"
        )
    finally:
        await connection.close()
    assert row is not None
    assert type(row["id"]).__module__.startswith("asyncpg")
    loaded = orjson.loads(
        dumps(
            camelize(
                {
                    "items": [
                        {"id": row["id"], "at": row["at"], "amount": row["amount"]},
                    ]
                }
            )
        )
    )
    assert loaded["items"][0]["id"] == str(row["id"])
    assert loaded["items"][0]["amount"] == "12.50"


async def test_eval_case_tags_are_saved(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    tenant = demo_id("tenant")
    suite_id = uuid.uuid4()
    case_id = uuid.uuid4()
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await save_eval_rows(
            session,
            {
                "eval_suites": [
                    {
                        "id": suite_id,
                        "tenant_id": tenant,
                        "name": "cert",
                        "description": "",
                        "kind": "functional",
                        "gate": {},
                    }
                ],
                "eval_cases": [
                    {
                        "id": case_id,
                        "tenant_id": tenant,
                        "suite_id": suite_id,
                        "name": "marker",
                        "input": {"text": "hello"},
                        "assertions": [],
                        "tool_mocks": [],
                        "tags": ["functional"],
                    }
                ],
            },
        )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        found = (
            await session.execute(
                text("SELECT tags FROM eval_cases WHERE id = :id"),
                {"id": case_id},
            )
        ).scalar_one()
    assert list(found) == ["functional"]
    await engine.dispose()

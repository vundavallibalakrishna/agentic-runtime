"""Two app instances share Valkey and Postgres. Proof label: contract (no model)."""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import timedelta

import pytest
from pydantic import SecretStr
from redis import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.ids import new_id
from ar_common.settings import BaseServiceSettings, EnvName
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.approvals.reviews import ReviewBook
from ar_domain.approvals.service import ApprovalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.process_state import install_shared_state, take_window
from ar_domain.readmodel.model import RepositoryReadModel

pytestmark = pytest.mark.integration


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


async def test_two_instances_share_durable_and_valkey_state(
    database_url: str, valkey_url: str
) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    connection = await engine.connect()
    try:
        found = (
            await connection.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).first()
    finally:
        await connection.close()
    assert found is not None
    tenant_id = found[0]
    client = Redis.from_url(valkey_url, decode_responses=True)
    first = RepositoryReadModel(database_url=database_url, allow_loopback=True)
    second = RepositoryReadModel(database_url=database_url, allow_loopback=True)
    first.valkey_client = client
    second.valkey_client = client
    settings = BaseServiceSettings(
        _env_file=None,
        env=EnvName.STAGING,
        cursor_secret=SecretStr("contract-cursor-secret"),
        valkey_url=valkey_url,
    )
    install_shared_state(first, settings)
    install_shared_state(second, settings)

    async with first.open(tenant_id) as unit:
        user_id = next(iter(unit.display_names))
        actor = Actor(tenant_id, user_id, PERMISSION_KEYS)
        unit.ensure_assistant(tenant_id, user_id)
        server_id = new_id()
        tool_id = new_id()
        now = utcnow()
        unit.tool_servers[server_id] = {
            "id": server_id,
            "tenant_id": tenant_id,
            "slug": "stage9http",
            "name": "Stage 9",
            "description": "",
            "kind": "builtin",
            "owner_user_id": user_id,
            "status": "approved",
            "disabled_at": None,
            "disabled_reason": None,
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        unit.tool_defs[tool_id] = {
            "id": tool_id,
            "tenant_id": tenant_id,
            "tool_server_id": server_id,
            "name": "ping",
            "qualified_name": "stage9http.ping",
            "disabled_at": None,
            "disabled_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        agent_id = unit.ensure_assistant(tenant_id, user_id)["id"]
        granted = ApprovalBook(unit).grant_standing(
            actor,
            {
                "tool_id": str(tool_id),
                "agent_id": str(agent_id),
                "expires_at": now + timedelta(days=7),
                "max_uses": 3,
            },
        )
        queue = ReviewBook(unit).create_queue(
            actor,
            {
                "slug": "files",
                "name": "Files",
                "subject_type": "file",
                "levels": [{"level": 1, "role": "reviewer"}],
            },
        )
        session_id = uuid.uuid4()
        unit.builder_sessions[session_id] = {
            "id": session_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "instruction": "shared builder",
            "messages": [{"role": "user", "text": "shared builder"}],
        }
        # Both hits name one minute, so the check does not depend on when the test runs.
        minute = time.time()
        first_hit = take_window(unit, f"agent-api:{tenant_id}", 3, now=minute)
        assert first_hit is not None and first_hit[0] is True

    async with second.open(tenant_id) as unit:
        queues = list(unit.review_queues.values())
        assert any(row.get("slug") == "files" for row in queues)
        assert queue["id"] in {str(row.get("id")) for row in queues} or any(
            row.get("id") == uuid.UUID(str(queue["id"])) for row in queues
        )
        standing = list(unit.standing_approvals.values())
        assert any(str(row.get("id")) == str(granted["id"]) for row in standing)
        loaded = unit.builder_sessions.get(session_id)
        assert isinstance(loaded, dict)
        assert loaded["instruction"] == "shared builder"
        second_hit = take_window(unit, f"agent-api:{tenant_id}", 3, now=minute)
        assert second_hit is not None
        assert second_hit[1] == 1

    for model in (first, second):
        held = getattr(model, "engine", None)
        if held is not None:
            await held.dispose()
    await engine.dispose()
    client.close()

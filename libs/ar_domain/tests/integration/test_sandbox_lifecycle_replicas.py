"""Two replicas sweep one database and act on a computer once. Proof: integration.

Real Postgres, Valkey and object store. The agent is the product's own, served in
process, and docker is stood in for at the launcher, so this proves what is saved and
what two replicas see of each other, not the container itself (the docker canary beside
this file does that).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.offload import run_sync
from ar_common.sandbox_docker import sandbox_labels
from ar_common.settings import BaseServiceSettings, get_settings, set_settings
from ar_common.valkey import valkey_sync_client
from ar_domain.identity.seed import apply
from ar_domain.readmodel.model import RepositoryReadModel
from ar_domain.sandboxes import runtime
from ar_domain.sandboxes.lifecycle import reconcile, scope_lock, sweep
from ar_domain.sandboxes.manager_launch import process_owner
from ar_domain.sandboxes.runtime import call_computer, ensure_scope

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration

_ENDPOINT = "http://computer.test"
_INSTALL = "replica-test-install"


class _Docker:
    """The one container host both replicas start their containers on."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.running: dict[str, dict[str, object]] = {}
        self.stopped: list[str] = []

    def start(
        self, name: str, token: str, sandbox_id: str = "", tenant_id: str = ""
    ) -> dict[str, object]:
        labels = sandbox_labels(
            install_id=_INSTALL, owner=process_owner(), sandbox_id=sandbox_id, tenant_id=tenant_id
        )
        self.running[name] = {
            "container_id": name,
            "name": name,
            "labels": labels,
            "created": time.time(),
        }
        return {"container_id": name, "endpoint_url": _ENDPOINT, "token": token}

    def stop(self, container_id: str) -> None:
        self.stopped.append(container_id)
        if self.running.pop(container_id, None) is not None:
            shutil.rmtree(self.root / "workspace", ignore_errors=True)

    def containers(self) -> list[dict[str, object]]:
        return [dict(item) for item in self.running.values()]

    def unlabelled(self) -> list[str]:
        return []


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


@pytest.fixture
def docker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Docker]:
    from ar_sandbox_agent.main import create_application

    box = tmp_path / "box"
    box.mkdir()
    monkeypatch.setenv("AR_SANDBOX_ROOT", str(box))
    monkeypatch.delenv("AR_SANDBOX_TOKEN", raising=False)
    monkeypatch.setenv("AR_INSTALL_ID", _INSTALL)
    monkeypatch.setenv("AR_SANDBOX_ORPHAN_GRACE_S", "0")
    monkeypatch.setattr(runtime, "_ROOT", tmp_path / "host")
    agent = create_application()
    monkeypatch.setattr(
        runtime.httpx, "Client", lambda **_kw: TestClient(agent, base_url=_ENDPOINT)
    )
    before = get_settings()
    set_settings(BaseServiceSettings())
    yield _Docker(box)
    set_settings(before)


async def _ensure(model: RepositoryReadModel, tenant: uuid.UUID, user: uuid.UUID) -> Any:
    """What the sandbox manager's ensure route does: lock the scope, load, ensure, save."""
    async with scope_lock(model, tenant, "conv:replicas"), model.open(tenant) as unit:
        row = await run_sync(
            ensure_scope,
            unit,
            tenant_id=tenant,
            template_slug="python-data",
            scope="conversation",
            scope_key="conv:replicas",
            conversation_id=None,
            agent_id=None,
            user_id=user,
        )
        return dict(row)


async def test_two_replicas_suspend_resume_and_end_a_computer_once(
    database_url: str, valkey_url: str, s3_endpoint: str, docker: _Docker
) -> None:
    del s3_endpoint
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    async with engine.connect() as connection:
        tenant = (
            await connection.execute(text("SELECT id FROM tenants WHERE slug = 'dev'"))
        ).scalar_one()
        user = (
            await connection.execute(
                text("SELECT id FROM users WHERE tenant_id = :tenant LIMIT 1"), {"tenant": tenant}
            )
        ).scalar_one()
    replicas = []
    for _ in range(2):
        model = RepositoryReadModel(database_url=database_url, allow_loopback=True)
        model.sandbox_launcher = docker
        model.valkey_client = valkey_sync_client(valkey_url)  # type: ignore[attr-defined]
        replicas.append(model)
    one, two = replicas

    made = await _ensure(one, tenant, user)
    sandbox_id = made["id"]
    wrote = call_computer(made, "write_file", {"path": "/workspace/note.txt", "content": "kept"})
    assert not wrote.get("is_error")
    assert await one.sandbox_states([sandbox_id]) == {sandbox_id: "ready"}
    assert await one.sandboxes_due() == []

    async def age(column: str) -> None:
        async with engine.begin() as connection:
            await connection.execute(
                text(f"UPDATE sandboxes SET {column} = now() - interval '2 days' WHERE id = :id"),  # noqa: S608
                {"id": sandbox_id},
            )

    # Idle for longer than the template allows. Both replicas sweep at the same moment;
    # the scope lock lets one act and shows the other what it saved.
    await age("last_active_at")
    assert await two.sandboxes_due() == [(tenant, sandbox_id, "conv:replicas")]
    swept = await asyncio.gather(sweep(one), sweep(two))
    assert sum(done["suspended"] for done in swept) == 1
    assert len(docker.stopped) == 1
    assert not docker.running
    async with engine.connect() as connection:
        saved = (
            await connection.execute(
                text(
                    "SELECT s.status, s.endpoint_url, f.kind, f.status FROM sandboxes s "
                    "JOIN files f ON f.id = s.snapshot_file_id WHERE s.id = :id"
                ),
                {"id": sandbox_id},
            )
        ).one()
    assert tuple(saved) == ("suspended", None, "sandbox_snapshot", "ready")
    # A suspended computer has no container, so one left running would be an orphan.
    assert await sweep(two) == {"suspended": 0, "terminated": 0, "removed": 0}

    # The other replica takes the next tool call: a new container, the folder put back.
    back = await _ensure(two, tenant, user)
    assert back["id"] == sandbox_id
    assert back["status"] == "ready"
    read = call_computer(back, "read_file", {"path": "/workspace/note.txt"})
    assert read["text"] == "kept"
    assert len(docker.running) == 1

    # A container whose computer has no row in the database is removed by either replica.
    docker.start("ar-sbx-norow", "t", sandbox_id=str(uuid.uuid4()), tenant_id=str(tenant))
    assert await reconcile(one) == 1
    assert "ar-sbx-norow" not in docker.running
    assert len(docker.running) == 1

    # Past its lifetime: ended once, and its container removed.
    await age("started_at")
    swept = await asyncio.gather(sweep(one), sweep(two))
    assert sum(done["terminated"] for done in swept) == 1
    assert not docker.running
    assert await two.sandbox_states([sandbox_id]) == {sandbox_id: "terminated"}
    async with engine.connect() as connection:
        actions = (
            await connection.execute(
                text("SELECT action FROM audit_events WHERE target_id = :id ORDER BY occurred_at"),
                {"id": str(sandbox_id)},
            )
        ).scalars()
        recorded = list(actions)
    assert recorded == [
        "sandbox.created",
        "sandbox.suspended",
        "sandbox.resumed",
        "sandbox.terminated",
    ]
    await engine.dispose()

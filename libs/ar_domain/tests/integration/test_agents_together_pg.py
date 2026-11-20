"""What agents that call each other leave in the database.

Two things failed on a database-backed install: a second file with the same bytes as an
earlier one could not be saved, and a message a run wrote for itself was stored as part
of the person's conversation.
"""

import hashlib
import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
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


async def test_two_written_files_with_the_same_bytes_and_a_runs_own_message_are_saved(
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
    slug = f"writer-{uuid.uuid4().hex[:8]}"
    agent = uuid.UUID(
        str(AgentLifecycle(store).create(actor, slug=slug, name="Writer", description="")["id"])
    )
    conversation = uuid.uuid4()
    store.conversations[conversation] = {
        "id": conversation,
        "tenant_id": tenant,
        "user_id": admin,
        "agent_id": agent,
        "title": "handover",
        "channel": "web",
        "status": "active",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    digest = hashlib.sha256(b"AGREED").hexdigest()
    files = []
    for name in ("handover.txt", "handover-again.txt"):
        file_id = uuid.uuid4()
        files.append(file_id)
        store.files[file_id] = {
            "id": file_id,
            "tenant_id": tenant,
            "owner_user_id": admin,
            "conversation_id": conversation,
            "kind": "artifact",
            "name": name,
            "mime_type": "text/plain",
            "size_bytes": 6,
            "sha256": digest,
            "object_key": f"tenants/{tenant}/artifact/{file_id}",
            "status": "ready",
            "scan_status": "skipped",
            "preview": {},
            "created_at": utcnow(),
            "deleted_at": None,
        }
    said, own = uuid.uuid4(), uuid.uuid4()
    for message_id, scope in ((said, "conversation"), (own, "run")):
        store.messages[message_id] = {
            "id": message_id,
            "tenant_id": tenant,
            "conversation_id": conversation,
            "role": "user",
            "content": [{"type": "text", "text": "hello"}],
            "text": "hello",
            "status": "completed",
            "scope": scope,
            "is_active_branch": scope == "conversation",
            "created_at": utcnow(),
        }
    await flush_store(store)
    try:
        async with engine.connect() as connection:
            kept = await connection.scalar(
                text("SELECT count(*) FROM files WHERE id = ANY(:ids)"), {"ids": files}
            )
            scopes = dict(
                (
                    await connection.execute(
                        text("SELECT id, scope FROM messages WHERE id = ANY(:ids)"),
                        {"ids": [said, own]},
                    )
                ).all()
            )
        assert kept == 2
        assert scopes == {said: "conversation", own: "run"}
    finally:
        # The database is shared with the other tests of this run: leave it as it was found.
        async with AsyncSession(engine) as session, session.begin():
            for statement in (
                "DELETE FROM files WHERE id = ANY(:files)",
                "DELETE FROM messages WHERE conversation_id = :conversation",
                "DELETE FROM conversations WHERE id = :conversation",
                "UPDATE agents SET draft_version_id = NULL, published_version_id = NULL "
                "WHERE id = :agent",
                "DELETE FROM agent_versions WHERE agent_id = :agent",
                "DELETE FROM agents WHERE id = :agent",
            ):
                await session.execute(
                    text(statement),
                    {"files": files, "conversation": conversation, "agent": agent},
                )
        await engine.dispose()

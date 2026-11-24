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


def _published(store: ChatService, actor: Actor, slug: str, **extra: object) -> uuid.UUID:
    """A published agent whose definition carries ``extra``."""
    life = AgentLifecycle(store)
    agent = uuid.UUID(str(life.create(actor, slug=slug, name=slug, description="")["id"]))
    draft = uuid.UUID(str(store.agents[agent]["draft_version_id"]))
    row = store.versions[draft]
    store.versions[draft] = {**row, "definition": {**dict(row["definition"]), **extra}}
    life.publish(actor, agent, skip_eval_gate=True)
    return agent


def _scripted(store: ChatService, helper: str, task: str, calls: list[str]) -> None:
    """Answer as a lead that calls its helper once, and as the helper given ``task``."""

    async def complete(messages, tools, *, tenant_id, model_alias):  # type: ignore[no-untyped-def]
        del tools, tenant_id, model_alias
        used = {"tokens_in": 3, "tokens_out": 5}
        mine = [str(row.get("content") or "") for row in messages if row.get("role") == "user"]
        if any(task in said for said in mine):
            calls.append("helper")
            return {"text": "REF-4471", "tool_calls": [], "usage": used}
        calls.append("lead")
        if any(row.get("role") == "tool" for row in messages):
            return {"text": "The reference is REF-4471.", "tool_calls": [], "usage": used}
        call = {"id": "c1", "name": "agents_call", "arguments": {"agent": helper, "task": task}}
        return {"text": "", "tool_calls": [call], "usage": used}

    store.complete_turn = complete  # type: ignore[method-assign]


async def test_a_called_agent_is_a_run_another_worker_can_carry_out(database_url: str) -> None:
    """One worker starts the call, a second runs the called agent, a third answers the call.

    Nothing passes between them but the database: the called agent's run, its task, its
    budget, who called whom, and the note of the call on the caller's checkpoint.
    """
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store as use_store
    from ar_testing.stand_in import shared

    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)

    async def process() -> ChatService:
        store = ChatService()
        assert await bind_store(store, database_url, tenant_slug="dev") is not None
        return store

    api = await process()
    tenant = api.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(api.tenant_binding.users.values()))  # type: ignore[union-attr]
    actor = Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")
    # An agent's draft names these aliases, and it is published only when each has a model.
    await shared().save_chat(
        api, tenant, script_set="called-agent-workers", aliases=("reasoning", "fast", "vision")
    )
    tag = uuid.uuid4().hex[:8]
    helper_slug = f"helper-{tag}"
    helper = _published(api, actor, helper_slug)
    lead = _published(
        api, actor, f"lead-{tag}", subagents={"allowed": [helper_slug], "max_depth": 2}
    )
    conversation = uuid.UUID(str(api.create_conversation(tenant, admin, lead)["id"]))
    posted = api.post_message(tenant, admin, conversation, "Find the reference.", schedule=False)
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await flush_store(api)
    task = f"LOOK-UP-{tag}"
    calls: list[str] = []
    # Three workers, started before the turn. None has seen the run or will see another's
    # memory. (A process that starts while a run is working marks it interrupted: OQ-193.)
    first, second, third = await process(), await process(), await process()
    try:
        _scripted(first, helper_slug, task, calls)
        use_store(first)
        kinds = []
        for _ in range(4):
            step = await advance_chat_step({"run_id": str(run_id), "text": "go"})
            kinds.append(step["kind"])
            if step["kind"] == "agents":
                break
        assert kinds[-1] == "agents", kinds
        (child,) = step["children"]
        child_id = uuid.UUID(str(child["run_id"]))
        async with engine.connect() as connection:
            saved = (
                await connection.execute(
                    text(
                        "SELECT status, agent_id, parent_run_id, trigger, "
                        "request ->> 'waits', request -> 'agent_chain' ->> 1 "
                        "FROM runs WHERE id = :id"
                    ),
                    {"id": child_id},
                )
            ).one()
        assert tuple(saved) == ("queued", helper, run_id, "subagent", "true", helper_slug)

        # A second worker has never seen either run. It carries out the called agent.
        _scripted(second, helper_slug, task, calls)
        use_store(second)
        for _ in range(4):
            step = await advance_chat_step({"run_id": str(child_id), "text": task})
            if step["kind"] == "final":
                break
        assert step == {"status": "completed", "kind": "final", "run_id": str(child_id)}

        # A third answers the call from what the second saved.
        _scripted(third, helper_slug, task, calls)
        use_store(third)
        for _ in range(4):
            step = await advance_chat_step({"run_id": str(run_id), "text": "go"})
            if step["kind"] == "final":
                break
        assert step["status"] == "completed"
        # The lead asked, the helper answered once, the lead went on. (What follows a
        # finished reply, such as deciding what to remember, also asks the lead's model.)
        assert calls[:3] == ["lead", "helper", "lead"]
        assert calls.count("helper") == 1
        async with engine.connect() as connection:
            rows = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT id, status || ':' || "
                            "coalesce(usage -> 'subagents' ->> 'runs', '0') "
                            "FROM runs WHERE id = ANY(:ids)"
                        ),
                        {"ids": [run_id, child_id]},
                    )
                ).all()
            )
            reply = await connection.scalar(
                text(
                    "SELECT content -> 0 ->> 'text' FROM messages "
                    "WHERE run_id = :id AND role = 'assistant'"
                ),
                {"id": run_id},
            )
            still_open = await connection.scalar(
                text("SELECT checkpoint -> 'agent_call' FROM runs WHERE id = :id"), {"id": run_id}
            )
        assert rows == {run_id: "completed:1", child_id: "completed:0"}
        assert reply == "The reference is REF-4471."
        assert still_open is None
    finally:
        use_store(None)
        async with AsyncSession(engine) as session, session.begin():
            for statement in (
                "DELETE FROM run_events WHERE run_id IN (SELECT id FROM runs "
                "WHERE conversation_id = :conversation)",
                "DELETE FROM run_steps WHERE run_id IN (SELECT id FROM runs "
                "WHERE conversation_id = :conversation)",
                "UPDATE conversations SET active_run_id = NULL WHERE id = :conversation",
                "DELETE FROM messages WHERE conversation_id = :conversation",
                "DELETE FROM runs WHERE conversation_id = :conversation",
                "DELETE FROM conversations WHERE id = :conversation",
                "UPDATE agents SET draft_version_id = NULL, published_version_id = NULL "
                "WHERE id = ANY(:agents)",
                "DELETE FROM agent_versions WHERE agent_id = ANY(:agents)",
                "DELETE FROM agents WHERE id = ANY(:agents)",
            ):
                await session.execute(
                    text(statement), {"conversation": conversation, "agents": [lead, helper]}
                )
        await engine.dispose()

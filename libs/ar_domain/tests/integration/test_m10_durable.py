"""HTTP product rows survive a process restart once Postgres is bound."""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_api.main import create_application
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.knowledge.book import KnowledgeBook
from ar_testing.stand_in import shared

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


def _seed_agents(store: ChatService, binding: object) -> None:
    """What the tenant seed does: the assistant and the builder exist, owned by the admin."""
    from ar_domain.agents.service import AgentLifecycle

    AgentLifecycle(store).ensure_builtins(
        binding.tenant_id,  # type: ignore[attr-defined]
        binding.users["admin@dev.local"],  # type: ignore[attr-defined]
    )


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    _alembic(url)
    return url


async def test_bind_flushes_chat_knowledge_memory_and_skills(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    store = ChatService()
    binding = await bind_store(store, database_url, tenant_slug="dev")
    assert binding is not None
    assert binding.tenant_id == demo_id("tenant")
    assert (binding.slug, binding.name, binding.plan) == ("dev", "Dev", "enterprise")
    assert store.durable is True
    # A store attached to a database starts with no agent: nothing is built in memory.
    assert store.agents == {}
    assert store.user_roles[binding.users["approver@dev.local"]] == {"approver"}
    assert store.display_names[binding.users["admin@dev.local"]] == "Dev Admin"
    _seed_agents(store, binding)
    admin_id = binding.users["admin@dev.local"]
    actor = Actor(binding.tenant_id, admin_id, PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    # A collection needs an embedding model, registered and saved as an administrator does.
    model_id = await shared().save_embeddings(store, binding.tenant_id)
    created = KnowledgeBook(store).create_collection(
        actor, {"slug": "handbook", "name": "Handbook"}
    )
    fact_id = uuid.uuid4()
    store.memory_facts[fact_id] = {
        "id": fact_id,
        "tenant_id": binding.tenant_id,
        "scope": "user",
        "user_id": admin_id,
        "content": "The desk opens at 08:30.",
        "category": "fact",
        "source_kind": "explicit",
        "trust_level": "high",
        "confidence": 1.0,
        "status": "active",
    }
    skill_id = uuid.uuid4()
    store.skills[skill_id] = {
        "id": skill_id,
        "tenant_id": binding.tenant_id,
        "slug": "desk-hours",
        "name": "Desk hours",
        "description": "When the desk opens",
        "owner_user_id": admin_id,
        "visibility": "tenant",
        "status": "draft",
    }
    await flush_store(store)
    async with engine.connect() as connection:
        agents = await connection.scalar(
            text("SELECT count(*) FROM agents WHERE tenant_id = :tenant"),
            {"tenant": binding.tenant_id},
        )
        collections = await connection.scalar(
            text(
                "SELECT count(*) FROM knowledge_collections "
                "WHERE slug = 'handbook' AND embedding_model_id = :model"
            ),
            {"model": model_id},
        )
        facts = await connection.scalar(
            text("SELECT count(*) FROM memory_facts WHERE id = :id"),
            {"id": fact_id},
        )
        skills = await connection.scalar(
            text("SELECT count(*) FROM skills WHERE id = :id"),
            {"id": skill_id},
        )
    await engine.dispose()
    assert agents >= 1
    assert collections == 1
    assert facts == 1
    assert skills == 1
    assert created["slug"] == "handbook"


async def test_worker_loads_new_conversation_and_restart_preserves_agent_edits(
    database_url: str,
) -> None:
    """The worker starts first, then reads a turn made in a separate API cache."""
    from ar_domain.durable.hydrate import reload_run
    from ar_runtime.activities.execute_chat_turn import execute_chat_turn
    from ar_runtime.activities.expire_approval import bind_store as bind_runtime

    api = ChatService(allow_loopback=True)
    binding = await bind_store(api, database_url, tenant_slug="dev")
    assert binding is not None
    # The tenant registers a chat model, saved to the database, so the worker that loads
    # the registry can answer the turn (M38a-T02e: there is no fake answer any more).
    await shared().save_chat(api, binding.tenant_id, script_set="m10-chat", aliases=("reasoning",))
    agent = next(row for row in api.agents.values() if row["slug"] == "assistant")
    agent["description"] = "An administrator changed this description"
    await flush_store(api)
    worker = ChatService(allow_loopback=True)
    await bind_store(worker, database_url, tenant_slug="dev")
    assert worker.agents[agent["id"]]["description"] == agent["description"]
    conversation = api.create_conversation(
        binding.tenant_id, binding.users["admin@dev.local"], agent["id"]
    )
    posted = api.post_message(
        binding.tenant_id,
        binding.users["admin@dev.local"],
        uuid.UUID(str(conversation["id"])),
        "hello from another process",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await flush_store(api)
    assert run_id not in worker.runs
    bind_runtime(worker)
    result = await execute_chat_turn({"run_id": str(run_id), "text": "hello from another process"})
    assert result["status"] == "completed"
    await reload_run(api, run_id)
    assert api.runs[run_id]["status"] == "completed"
    assert api.conversations[uuid.UUID(str(conversation["id"]))]["active_run_id"] is None
    assert api.events[run_id][-1]["type"] == "run.completed"
    assistant_id = api.runs[run_id]["assistant_message_id"]
    assert "hello from another process" in api.messages[assistant_id]["text"]
    event_count = len(worker.events[run_id])
    retried = await execute_chat_turn({"run_id": str(run_id), "text": "must not run twice"})
    assert retried["status"] == "completed"
    assert len(worker.events[run_id]) == event_count
    await api.durable_engine.dispose()
    await worker.durable_engine.dispose()
    bind_runtime(None)


async def test_widget_credentials_and_user_status_survive_restart(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real encrypted backend and tenant-scoped identity lookup back embedded chat."""
    import base64
    from types import SimpleNamespace

    import httpx
    from pydantic import SecretStr

    from ar_common.time import utcnow
    from ar_domain.channels.book import ChannelBook
    from ar_domain.channels.posts import load_credentials
    from ar_domain.channels.widget_auth import sign_widget_token

    monkeypatch.setattr(
        "ar_domain.secrets.cached.get_settings",
        lambda: SimpleNamespace(
            secrets_backend="db_encrypted",
            db_encryption_keys=SecretStr('{"k1":"' + base64.b64encode(b"t" * 32).decode() + '"}'),
            db_encryption_active_key="k1",
        ),
    )
    store = ChatService()
    binding = await bind_store(store, database_url, tenant_slug="dev")
    assert binding is not None
    store.tenant_settings[binding.tenant_id] = {"features": {"widget": True}}
    actor = Actor(binding.tenant_id, binding.users["admin@dev.local"], PERMISSION_KEYS)
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    created = ChannelBook(store).create(
        actor,
        {
            "kind": "widget",
            "name": "Durable portal",
            "default_agent_id": agent["id"],
            "config": {"allowedOrigins": ["https://portal.example"]},
            "credentials": {"widget_secret": "persisted-test-signing-secret"},
        },
    )
    await flush_store(store)
    restarted = ChatService()
    await bind_store(restarted, database_url, tenant_slug="dev")
    integration_id = uuid.UUID(str(created["id"]))
    assert (
        load_credentials(restarted, restarted.channel_integrations[integration_id])["widget_secret"]
        == "persisted-test-signing-secret"  # noqa: S105
    )
    restarted.tenant_settings[binding.tenant_id] = {"features": {"widget": True}}
    restarted._bind_attempted = True
    app = create_application()
    app.state.chat = restarted
    app.state.await_runs = True
    token = sign_widget_token(
        secret="persisted-test-signing-secret",  # noqa: S106
        audience=f"ar-widget:{integration_id}",
        email="admin@dev.local",
        name="Admin",
        exp=int(utcnow().timestamp()) + 120,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://localhost:3000"
    ) as client:
        issued = await client.post(
            "/api/v1/widget/sessions", json={"integrationId": str(integration_id), "token": token}
        )
        assert issued.status_code == 204, issued.text
        assert (await client.get("/api/v1/widget/session")).status_code == 200
        async with restarted.durable_engine.begin() as connection:
            await connection.execute(
                text("UPDATE users SET status = 'suspended' WHERE id = :id"), {"id": actor.user_id}
            )
        assert (await client.get("/api/v1/widget/session")).status_code == 401
        async with restarted.durable_engine.begin() as connection:
            await connection.execute(
                text("UPDATE users SET status = 'active' WHERE id = :id"), {"id": actor.user_id}
            )
    async with restarted.durable_engine.connect() as connection:
        count = await connection.scalar(
            text(
                "SELECT count(*) FROM audit_events WHERE tenant_id = :tenant "
                "AND action = 'auth.login' AND detail->>'channel' = 'widget'"
            ),
            {"tenant": binding.tenant_id},
        )
        assert count >= 1
    ChannelBook(restarted).delete(actor, integration_id)
    await flush_store(restarted)
    after_delete = ChatService()
    await bind_store(after_delete, database_url, tenant_slug="dev")
    assert integration_id not in after_delete.channel_integrations
    await after_delete.durable_engine.dispose()
    await store.durable_engine.dispose()
    await restarted.durable_engine.dispose()


async def test_password_login_uses_persisted_non_demo_user_and_permissions(
    database_url: str,
) -> None:
    """A persisted non-demo user signs in with their password and gets durable rows."""
    import httpx

    from ar_domain.db.context import Principal, TenantContext
    from ar_domain.db.session import tenant_session
    from ar_domain.identity.models import RoleAssignment, User
    from ar_domain.identity.passwords import hash_password
    from ar_domain.identity.repository import IdentityRepository

    store = ChatService()
    binding = await bind_store(store, database_url, tenant_slug="dev")
    assert binding is not None
    email = f"retained-{uuid.uuid4().hex[:8]}@dev.local"
    user_id = uuid.uuid4()
    ctx = TenantContext.from_principal(
        Principal(kind="system", id="test", tenant_id=binding.tenant_id), "login-test"
    )
    async with tenant_session(ctx, engine=store.durable_engine) as session:
        repo = IdentityRepository(session, ctx)
        member = await repo.get_role_by_key("member")
        assert member is not None
        repo.add(
            User(
                id=user_id,
                tenant_id=binding.tenant_id,
                idp_subject=email,
                email=email,
                display_name="Retained identity",
                status="active",
                password_hash=hash_password("retained-pw"),
            )
        )
        await session.flush()
        repo.add(
            RoleAssignment(
                tenant_id=binding.tenant_id,
                role_id=member.id,
                principal_type="user",
                principal_id=user_id,
                scope_type="tenant",
            )
        )
    app = create_application()
    store._bind_attempted = True
    app.state.chat = store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "retained-pw"}
        )
        assert response.status_code == 200, response.text
        profile = (await client.get("/api/v1/auth/session")).json()
        assert profile["user"]["id"] == str(user_id)
        assert profile["tenant"]["id"] == str(binding.tenant_id)
        assert profile["user"]["displayName"] == "Retained identity"
        assert profile["roles"] == ["member"]
        assert "tenant:manage" not in profile["permissions"]
        conversation = await client.post(
            "/api/v1/conversations",
            json={},
            headers={"origin": "http://localhost:3000", "x-csrf-token": profile["csrfToken"]},
        )
        assert conversation.status_code == 200, conversation.text
    async with store.durable_engine.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT user_id FROM conversations WHERE id = :id"),
                {"id": uuid.UUID(conversation.json()["id"])},
            )
            == user_id
        )
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE actor_id = :id "
                    "AND action = 'auth.login'"
                ),
                {"id": str(user_id)},
            )
            >= 1
        )
    await store.durable_engine.dispose()


async def test_routine_runs_across_api_system_and_runtime_process_stores(
    database_url: str, temporal_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A newly created routine persists, executes, reloads and cannot run twice on retry."""
    from temporalio.worker import Worker

    from ar_domain.durable.hydrate import reload_routines, reload_run
    from ar_domain.routines.book import RoutineBook
    from ar_domain.routines.dispatch import start_run
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.execute_chat_turn import execute_chat_turn, finish_chat_turn
    from ar_runtime.activities.expire_approval import bind_store as bind_runtime
    from ar_runtime.workflows.turn import TurnWorkflow
    from ar_system.routines_store import bind_store as bind_system
    from ar_system.workflows.routine_run import (
        RoutineRunWorkflow,
        accept_activity,
        complete_activity,
        prepare_activity,
    )

    api, system, runtime = (
        ChatService(allow_loopback=True),
        ChatService(allow_loopback=True),
        ChatService(allow_loopback=True),
    )
    await bind_store(api, database_url, tenant_slug="dev")
    binding = api.tenant_binding
    # Register a chat model and save it, so the system and runtime stores load it when they
    # bind and the routine's turn can answer (M38a-T02e: no fake answer any more). The
    # stand-in is scripted to give the worker reply the assertions expect.
    shared().script("m10-routine", [{"match": {}, "respond": {"text": "Actual worker reply"}}])
    await shared().save_chat(
        api, binding.tenant_id, script_set="m10-routine", aliases=("reasoning",)
    )
    for store in (system, runtime):
        await bind_store(store, database_url, tenant_slug="dev")
    actor = Actor(binding.tenant_id, binding.users["admin@dev.local"], PERMISSION_KEYS)
    assistant = next(row for row in api.agents.values() if row["slug"] == "assistant")
    created = RoutineBook(api).create(
        actor,
        {
            "name": "Durable routine",
            "agent_id": assistant["id"],
            "instructions": "Give an update",
            "trigger": {"type": "manual"},
            "delivery": [{"type": "conversation"}],
        },
    )
    routine_id = uuid.UUID(str(created["id"]))
    assert routine_id not in system.routines
    started = RoutineBook(api).run_now(actor, routine_id, {}, execute=False)
    run_id = uuid.UUID(str(started["run_id"]))
    assert api.runs[run_id]["status"] == "queued"
    assert api.runs[run_id]["assistant_message_id"] in api.messages
    bind_system(system)
    bind_runtime(runtime)
    api.temporal_client = temporal_env.client
    async with (
        Worker(
            temporal_env.client,
            task_queue="ar-system",
            workflows=[RoutineRunWorkflow],
            activities=[accept_activity, prepare_activity, complete_activity],
        ),
        Worker(
            temporal_env.client,
            task_queue="ar-runtime",
            workflows=[TurnWorkflow],
            activities=[execute_chat_turn, advance_chat_step, finish_chat_turn],
        ),
    ):
        await start_run(api, run_id)
        event = next(row for row in api.routine_events.values() if row.get("run_id") == run_id)
        result = await temporal_env.client.get_workflow_handle(
            f"routine-event-{event['id']}"
        ).result()
        assert result["status"] == "completed"
        await reload_run(api, run_id)
        await reload_routines(api)
        assert api.runs[run_id]["result_summary"] == "Actual worker reply"
        assert api.routine_events[event["id"]]["status"] == "started"
        again = await prepare_activity(
            {"routine_id": str(routine_id), "event_id": str(event["id"])}
        )
        assert again["run_id"] == str(run_id)
        assert api.routines[routine_id]["last_run_at"] is not None
    for store in (api, system, runtime):
        await store.durable_engine.dispose()
    bind_runtime(None)
    bind_system(None)

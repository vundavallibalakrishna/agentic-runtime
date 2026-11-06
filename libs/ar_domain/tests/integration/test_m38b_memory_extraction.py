"""A worker remembers from a turn it loaded from the database, and saves it.

Task: M38b-T12. On a real stack the turn runs in a worker that reloads the run from
Postgres. The fact it extracts must be written to the database: its source reference then
carries the driver's own id type, which the JSON encoder used to reject, so nothing a live
chat remembered was ever saved.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.durable.hydrate import reload_memory, reload_run
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.memory.book import MemoryBook
from ar_testing.stand_in import shared

pytestmark = pytest.mark.integration

SCRIPT_SET = "m38b-worker-memory"
SAID = "My sister Odile runs the Lyon warehouse. Who should I ask about pallets?"


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)
    url = url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def _process(database_url: str) -> ChatService:
    """A product store attached to the dev tenant, as one API or worker process holds it."""
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    return store


async def test_a_worker_remembers_from_a_turn_it_reloaded(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    api = await _process(database_url)
    binding = api.tenant_binding
    assert binding is not None
    tenant = binding.tenant_id
    admin = binding.users["admin@dev.local"]
    AgentLifecycle(api).ensure_builtins(tenant, admin)

    # The administrator's models: a chat model that also decides what to remember, and an
    # embedding model. The stand-in answers the turn, and names one lasting fact from it.
    shared().script(
        SCRIPT_SET,
        [
            {
                "match": {
                    "system_contains": "You decide what an assistant should remember",
                    "contains": "Odile",
                },
                "respond": {
                    "text": '[{"op": "add", "content": "Has a sister called Odile", '
                    '"category": "contact", "scope": "user", "confidence": 0.9, '
                    '"explicit": false}]'
                },
            },
            {
                "match": {"system_contains": "You decide what an assistant should remember"},
                "respond": {"text": "[]"},
            },
            {"match": {}, "respond": {"text": "Ask the warehouse lead."}},
        ],
    )
    await shared().save_embeddings(api, tenant)
    await shared().save_chat(api, tenant, script_set=SCRIPT_SET)

    conversation = api.create_conversation(tenant, admin, None)
    posted = api.post_message(
        tenant, admin, uuid.UUID(str(conversation["id"])), SAID, schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await flush_store(api)

    # The worker is another process: it loads the run from the database and runs the turn.
    worker = await _process(database_url)
    await reload_run(worker, run_id)
    await worker.generate(run_id, SAID, [])
    assert worker.runs[run_id]["status"] == "completed"
    assert worker.runs[run_id]["memory_extraction"]["saved"] == 1
    await flush_store(worker)

    async with engine.connect() as connection:
        saved = (
            await connection.execute(
                text(
                    "SELECT content, source_kind, source_ref ->> 'run_id' FROM memory_facts "
                    "WHERE tenant_id = :tenant AND content = 'Has a sister called Odile'"
                ),
                {"tenant": tenant},
            )
        ).one()
    assert tuple(saved) == ("Has a sister called Odile", "extracted", str(run_id))

    # A process that starts later has the memory.
    later = await _process(database_url)
    actor = Actor(tenant, admin, PERMISSION_KEYS)
    assert "Has a sister called Odile" in [
        str(item["content"]) for item in MemoryBook(later).list_user(actor)
    ]

    # The API process was running all along. Its Memory screen shows what the worker saved.
    fact_id = next(
        key
        for key, row in worker.memory_facts.items()
        if row.get("content") == "Has a sister called Odile"
    )
    assert fact_id not in api.memory_facts
    await reload_memory(api)
    assert api.memory_facts[fact_id]["content"] == "Has a sister called Odile"

    # The person deletes it there. The worker must not go on recalling it.
    MemoryBook(api).delete_user(actor, uuid.UUID(str(fact_id)))
    await flush_store(api)
    assert fact_id in worker.memory_facts
    await reload_run(worker, run_id)
    assert fact_id not in worker.memory_facts

    # A setting the administrator changes reaches the worker before its next turn.
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE tenants SET settings = jsonb_set(settings, '{memory}', "
                "'{\"extraction\": false}'::jsonb) WHERE id = :tenant"
            ),
            {"tenant": tenant},
        )
    assert MemoryBook(worker).extraction_wanted({**worker.runs[run_id], "id": uuid.uuid4()})
    await reload_run(worker, run_id)
    assert not MemoryBook(worker).extraction_wanted({**worker.runs[run_id], "id": uuid.uuid4()})
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE tenants SET settings = settings - 'memory' WHERE id = :tenant"),
            {"tenant": tenant},
        )

    for store in (api, worker, later):
        if store.durable_engine is not None:
            await store.durable_engine.dispose()
    await engine.dispose()

"""A file uploaded through the API reaches the worker that runs the turn.

Task: M38b-T08. On a real stack the upload and the message are handled by the API and the
turn by a worker. The worker learned which files exist only when it started, so a file
uploaded later was unknown to it: the prompt could not name it and no tool could read it.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.durable.hydrate import reload_run
from ar_domain.files.attachments import conversation_attachments
from ar_domain.identity.seed import apply
from ar_domain.memory.session import prepare_prompt
from ar_domain.tools.general import dispatch_general

pytestmark = pytest.mark.integration

CSV = b"region,total\nnorth,120\nsouth,80\n"


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


async def test_a_worker_reads_a_file_uploaded_after_it_started(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    api = await _process(database_url)
    binding = api.tenant_binding
    assert binding is not None
    tenant = binding.tenant_id
    admin = binding.users["admin@dev.local"]
    AgentLifecycle(api).ensure_builtins(tenant, admin)
    await flush_store(api)

    # The worker is already running when the person uploads a file and sends a message.
    worker = await _process(database_url)
    conversation_id = uuid.UUID(str(api.create_conversation(tenant, admin, None)["id"]))
    name = f"orders-{uuid.uuid4().hex[:8]}.csv"
    file_id = uuid.UUID(str(api.upload(tenant, admin, name, "text/csv", CSV)["id"]))
    posted = api.post_message(
        tenant,
        admin,
        conversation_id,
        "Total this by region",
        attachment_ids=[file_id],
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await flush_store(api)
    assert file_id not in worker.files, "the worker has not heard of the file yet"

    await reload_run(worker, run_id)

    (found,) = conversation_attachments(worker, conversation_id)
    assert (found.file_id, found.name, found.path) == (file_id, name, f"inputs/{name}")
    assert found.size_bytes == len(CSV)
    run = worker.runs[run_id]
    conversation = worker.conversations[conversation_id]
    version = worker.versions[worker.agents[conversation["agent_id"]]["published_version_id"]]
    prepare_prompt(worker, run, conversation, version["definition"], "Total this by region")
    asked = run["prompt_messages"][-1]["content"]
    assert f"id={file_id} path=inputs/{name}" in asked
    read = dispatch_general(
        worker,
        "read_file",
        {
            "_tenant_id": tenant,
            "_user_id": admin,
            "_run_id": run_id,
            "_conversation_id": conversation_id,
            "path": f"inputs/{name}",
        },
    )
    assert read["is_error"] is False, read["text"]
    assert "north,120" in str(read["text"])

    # What the worker's tool wrote is found by the API, which serves the download.
    wrote = dispatch_general(
        worker,
        "write_file",
        {
            "_tenant_id": tenant,
            "_user_id": admin,
            "_run_id": run_id,
            "_conversation_id": conversation_id,
            "path": "totals.txt",
            "content": "north 120, south 80",
        },
    )
    made = uuid.UUID(str(wrote["structured"]["presentation"]["files"][0]["file_id"]))
    await flush_store(worker)
    assert made not in api.files
    await reload_run(api, run_id)
    assert api.files[made]["name"] == "totals.txt"
    assert bytes(api.blobs[made]) == b"north 120, south 80"

    for store in (api, worker):
        if store.durable_engine is not None:
            await store.durable_engine.dispose()
    await engine.dispose()

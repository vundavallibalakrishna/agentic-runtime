"""Every accepted upload is kept, in the object store, and read where it is needed.

Task: M38b-T13. An upload over 8 MiB used to live only in the memory of the process that
received it, never reached a worker and was lost on restart; the ``files`` table was
never written and the bytes sat in a Postgres row. Now the row is in ``files`` and the
bytes are an object in the S3-compatible store the install names.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.errors import ArError
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService
from ar_domain.durability.store import read_blob, workspace_root
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.durable.hydrate import reload_run
from ar_domain.files.objects import object_store
from ar_domain.identity.seed import apply
from ar_domain.tools.general import dispatch_general
from ar_testing.objects import RefusingObjectStore

pytestmark = pytest.mark.integration

TWENTY_MIB = 20 * 1024 * 1024


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


async def test_a_large_upload_reaches_the_worker_and_survives_a_restart(
    database_url: str, s3_endpoint: str
) -> None:
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
    assert object_store(api).endpoint == s3_endpoint  # type: ignore[attr-defined]

    # A PDF of twenty megabytes, well over the eight the old Postgres row allowed.
    body = b"%PDF-1.4\n" + os.urandom(TWENTY_MIB - 9)
    name = f"scan-{uuid.uuid4().hex[:8]}.pdf"
    worker = await _process(database_url)
    conversation_id = uuid.UUID(str(api.create_conversation(tenant, admin, None)["id"]))
    uploaded = api.upload(tenant, admin, name, "application/pdf", body)
    file_id = uuid.UUID(str(uploaded["id"]))
    posted = api.post_message(
        tenant, admin, conversation_id, "Read this", attachment_ids=[file_id], schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await flush_store(api)

    # The row is in the files table, with no bytes; the bytes are one object in the store.
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT size_bytes, object_key, status FROM files WHERE id = :id"),
                {"id": file_id},
            )
        ).all()
        blobs = (
            await connection.execute(
                text("SELECT count(*) FROM file_blob_payloads WHERE id = :id"), {"id": file_id}
            )
        ).scalar()
    assert len(rows) == 1
    size, key, status = rows[0]
    assert (size, status) == (TWENTY_MIB, "ready")
    assert blobs == 0
    assert object_store(api).get(str(key)) == body

    # The worker, already running, has the whole file in the turn's folder: the first
    # tool call puts every attached file at the path the prompt names.
    assert file_id not in worker.files
    await reload_run(worker, run_id)
    assert file_id in worker.files
    assert file_id not in worker.blobs, "a row comes in; bytes are fetched when needed"
    listed = dispatch_general(
        worker,
        "list_files",
        {
            "_tenant_id": tenant,
            "_user_id": admin,
            "_run_id": run_id,
            "_conversation_id": conversation_id,
            "path": "inputs",
        },
    )
    assert listed["is_error"] is False, listed["text"]
    assert name in str(listed["text"])
    assert (workspace_root(run_id) / "workspace" / "inputs" / name).stat().st_size == TWENTY_MIB
    assert read_blob(worker, file_id) == body

    # Every process restarts: a new API process serves the download from the store.
    for store in (api, worker):
        if store.durable_engine is not None:
            await store.durable_engine.dispose()
    restarted = await _process(database_url)
    assert file_id in restarted.files, "the row is loaded with the tenant"
    assert file_id not in restarted.blobs, "the bytes are not"
    data, mime = restarted.file_bytes(tenant, admin, file_id)
    assert (len(data), mime) == (TWENTY_MIB, "application/pdf")
    assert data == body

    # Deleting is soft: the row says so and the download is gone; the object waits for
    # the retention sweep.
    restarted.delete_file(tenant, admin, file_id)
    await flush_store(restarted)
    async with engine.connect() as connection:
        deleted = (
            await connection.execute(
                text("SELECT status, deleted_at FROM files WHERE id = :id"), {"id": file_id}
            )
        ).one()
    assert deleted[0] == "deleted"
    assert deleted[1] is not None
    assert read_blob(restarted, file_id) is None
    if restarted.durable_engine is not None:
        await restarted.durable_engine.dispose()
    await engine.dispose()


async def test_an_upload_the_object_store_refuses_is_not_a_file(database_url: str) -> None:
    api = await _process(database_url)
    binding = api.tenant_binding
    assert binding is not None
    tenant = binding.tenant_id
    admin = binding.users["admin@dev.local"]
    api.objects = RefusingObjectStore()
    before = set(api.files)
    with pytest.raises(ArError, match="AR_S3_ENDPOINT") as refused:
        api.upload(tenant, admin, "note.txt", "text/plain", b"hello")
    assert refused.value.code.value == "unavailable"
    assert set(api.files) == before, "no row without its bytes"
    if api.durable_engine is not None:
        await api.durable_engine.dispose()


async def test_a_file_from_before_moves_to_the_object_store_on_its_first_read(
    database_url: str, s3_endpoint: str
) -> None:
    """A release before this one kept bytes in ``file_blobs``; those files stay readable."""
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    first = await _process(database_url)
    binding = first.tenant_binding
    assert binding is not None
    tenant = binding.tenant_id
    admin = binding.users["admin@dev.local"]
    old_id = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO files (id, tenant_id, owner_user_id, kind, name, mime_type, "
                "size_bytes, sha256, object_key, status, scan_status) VALUES (:id, :tenant_id, "
                ":owner, 'upload', 'orders.csv', 'text/csv', 12, 'x', :key, 'ready', 'skipped')"
            ),
            {
                "id": old_id,
                "tenant_id": tenant,
                "owner": admin,
                "key": f"legacy/file-blobs/{old_id}",
            },
        )
        await connection.execute(
            text(
                "INSERT INTO file_blob_payloads (id, tenant_id, body) "
                "VALUES (:id, :tenant_id, :body)"
            ),
            {"id": old_id, "tenant_id": tenant, "owner": admin, "body": b"a,b\n1,2\n3,4\n"},
        )
    if first.durable_engine is not None:
        await first.durable_engine.dispose()

    # A process started after the change moves the old file to the object store when the
    # tenant is hydrated: the row is in ``files`` and the object is written.
    restarted = await _process(database_url)
    assert old_id in restarted.files
    assert restarted.files[old_id]["name"] == "orders.csv"
    key = str(restarted.files[old_id]["object_key"])
    assert object_store(restarted).get(key) == b"a,b\n1,2\n3,4\n"

    # The file reads back and the row is written to ``files``; the blob row is not consulted.
    data, mime = restarted.file_bytes(tenant, admin, old_id)
    assert (data, mime) == (b"a,b\n1,2\n3,4\n", "text/csv")
    await flush_store(restarted)
    async with engine.connect() as connection:
        moved = (
            await connection.execute(
                text("SELECT object_key, size_bytes FROM files WHERE id = :id"), {"id": old_id}
            )
        ).all()
    assert moved == [(key, 12)]

    # A second process does not move it again: the ``files`` row is found first.
    third = await _process(database_url)
    assert object_store(third).get(key) == data
    if restarted.durable_engine is not None:
        await restarted.durable_engine.dispose()
    if third.durable_engine is not None:
        await third.durable_engine.dispose()
    await engine.dispose()

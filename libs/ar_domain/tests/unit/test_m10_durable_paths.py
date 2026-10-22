"""Exercise the durable cutover without a database.

The unit gate counts these modules. A fake session stands in for Postgres so
the row builders, the hydrate merge, and the worker loops all run.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from ar_common.time import utcnow
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.durable import bind as bind_mod
from ar_domain.durable import flush as flush_mod
from ar_domain.durable import hydrate as hydrate_mod
from ar_domain.durable.bind import (
    DevBinding,
    _connect,
    _id_map,
    _lookup,
    _remap,
    _remap_agents,
    bind_store,
    binding_from,
    should_bind,
    user_for_email,
)
from ar_domain.durable.codec import (
    as_bool,
    as_dt,
    as_int,
    as_json,
    as_text,
    as_uuid,
    as_vector,
    row_dict,
)
from ar_domain.durable.flush import event_tenant, flush_store, mark_all_dirty, schedule_flush
from ar_domain.durable.hydrate import hydrate_tenant, reload_document, reload_run
from ar_domain.durable.tracking import TrackedDict, TrackedList, install_tracking
from ar_domain.knowledge.pipeline import (
    WORKFLOW_MAX_BYTES,
    _delete_stored_chunks,
    ingest_document,
    ingest_or_enqueue,
)
from ar_domain.knowledge.store import active_index


class _Engine:
    """Stand-in that the patched AsyncEngine check accepts."""

    def __init__(self) -> None:
        self.disposed = False

    def connect(self) -> _Conn:
        return _Conn()

    async def dispose(self) -> None:
        self.disposed = True


class _Conn:
    async def __aenter__(self) -> _Conn:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        return None


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def mappings(self) -> _Rows:
        return self

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def __iter__(self) -> Any:
        return iter(self._rows)


class _Session:
    """Accepts every statement. The first execute fails so the skip path runs."""

    raise_once = True

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.calls = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    def begin(self) -> _Session:
        return self

    def begin_nested(self) -> _Session:
        return self

    async def execute(self, statement: object, params: object = None) -> _Rows:
        del params
        self.calls += 1
        if _Session.raise_once and self.calls == 1:
            _Session.raise_once = False
            raise RuntimeError("row rejected")
        return _Rows(_rows_for(str(statement)))

    async def scalar(self, *_args: object, **_kwargs: object) -> uuid.UUID:
        return _TENANT


_TENANT = uuid.uuid4()
_USER = uuid.uuid4()
_AGENT = uuid.uuid4()
_VERSION = uuid.uuid4()
_RUN = uuid.uuid4()
_DOC = uuid.uuid4()
_COLLECTION = uuid.uuid4()
_CHUNK = uuid.uuid4()


def _rows_for(sql: str) -> list[dict[str, Any]]:
    now = utcnow()
    if "document_chunks" in sql:
        return [{"id": _CHUNK, "text": "chunk", "ordinal": 0}]
    if "knowledge_collections" in sql:
        return [{"id": _COLLECTION, "slug": "handbook"}]
    if "FROM runs WHERE id" in sql:
        return [
            {
                "id": _RUN,
                "conversation_id": _AGENT,
                "tenant_id": _TENANT,
                "status": "completed",
            }
        ]
    if "messages" in sql:
        return [{"id": _USER, "content": [{"text": "hello"}], "created_at": now}]
    if "run_events" in sql:
        return [
            {
                "run_id": _RUN,
                "seq": 1,
                "type": "run.completed",
                "data": {"ok": True},
                "created_at": now,
                "tenant_id": _TENANT,
            }
        ]
    if "memory_facts" in sql:
        return [{"id": _USER, "embedding": [0.2, 0.4]}]
    if "tool_versions" in sql:
        return [{"id": _VERSION, "embedding": (0.1, 0.2)}]
    if "tool_server_versions" in sql:
        return [{"id": _VERSION}]
    if "tool_servers" in sql:
        return [{"id": _AGENT, "slug": "desk"}]
    if "FROM tools" in sql:
        return [{"id": _CHUNK, "name": "lookup"}]
    if "agent_versions" in sql:
        return [{"id": _VERSION, "definition": {}}]
    if "skill_versions" in sql:
        return [{"id": _VERSION}]
    if "FROM skills" in sql:
        return [{"id": _AGENT, "slug": "status"}]
    if "knowledge_sources" in sql:
        return [{"id": _DOC}]
    if "FROM documents" in sql:
        return [{"id": _DOC, "collection_id": _COLLECTION, "title": "Handbook"}]
    if "FROM agents" in sql:
        return [{"id": _AGENT, "slug": "assistant", "disabled_at": now}]
    if "conversations" in sql:
        return [{"id": _AGENT, "title": "Weekly"}]
    if "FROM runs" in sql:
        return [{"id": _RUN, "conversation_id": _AGENT, "status": "completed"}]
    return []


def _patch_engines(monkeypatch: pytest.MonkeyPatch) -> _Engine:
    engine = _Engine()
    for module in (flush_mod, hydrate_mod):
        monkeypatch.setattr(module, "AsyncEngine", _Engine)
        monkeypatch.setattr(module, "AsyncSession", _Session)
    return engine


def _seed(service: ChatService) -> None:
    tenant = demo_id("tenant")
    now = utcnow()
    vector = [0.0] * 1024
    install_tracking(service)
    service.agents[_AGENT] = {
        "id": _AGENT,
        "tenant_id": tenant,
        "slug": "weekly",
        "name": "Weekly",
        "published_version_id": _VERSION,
        "draft_version_id": _VERSION,
        "disabled": False,
    }
    service.versions[_VERSION] = {
        "id": _VERSION,
        "tenant_id": tenant,
        "agent_id": _AGENT,
        "version": 1,
        "state": "published",
        "definition": {"name": "Weekly"},
        "definition_hash": "",
    }
    service.skills[_AGENT] = {"id": _AGENT, "tenant_id": tenant, "slug": "brief"}
    service.skill_versions[_VERSION] = {
        "id": _VERSION,
        "tenant_id": tenant,
        "skill_id": _AGENT,
        "required_tools": ["knowledge.search"],
        "assets": [],
        "instructions_md": "Summarise the week.",
    }
    service.knowledge_collections[_COLLECTION] = {
        "id": _COLLECTION,
        "tenant_id": tenant,
        "slug": "handbook",
        "chunking": {"target_tokens": 128},
        "stats": {},
    }
    service.knowledge_sources[_DOC] = {
        "id": _DOC,
        "tenant_id": tenant,
        "collection_id": _COLLECTION,
        "config": {},
        "cursor": {},
    }
    service.knowledge_documents[_DOC] = {
        "id": _DOC,
        "tenant_id": tenant,
        "collection_id": _COLLECTION,
        "source_id": _DOC,
        "acl_principals": ["user:ada"],
        "status": "indexed",
        "error": "none",
    }
    service.document_chunks[_CHUNK] = {
        "id": _CHUNK,
        "tenant_id": tenant,
        "document_id": _DOC,
        "heading_path": ["Week"],
        "page_from": 1,
        "page_to": 2,
        "text": "The desk opens at nine.",
    }
    service.memory_facts[_USER] = {
        "id": _USER,
        "tenant_id": tenant,
        "content": "Ada prefers morning digests.",
        "confidence": 0.9,
        "embedding": vector,
        "source_kind": "explicit",
        "source_ref": {"kind": "user"},
    }
    service.tool_servers[_AGENT] = {
        "id": _AGENT,
        "tenant_id": tenant,
        "slug": "desk",
        "disabled_reason": "off",
    }
    service.tool_server_versions[_VERSION] = {
        "id": _VERSION,
        "tenant_id": tenant,
        "tool_server_id": _AGENT,
        "manifest": {"name": "desk"},
        "config": {},
    }
    service.tool_defs[_CHUNK] = {
        "id": _CHUNK,
        "tenant_id": tenant,
        "tool_server_id": _AGENT,
        "name": "lookup",
        "disabled_reason": "off",
    }
    service.tool_versions[_VERSION] = {
        "id": _VERSION,
        "tenant_id": tenant,
        "tool_id": _CHUNK,
        "tool_server_version_id": _VERSION,
        "input_schema": {},
        "annotations": {},
        "embedding": vector,
        "approval_preview": {},
    }
    service.conversations[_AGENT] = {
        "id": _AGENT,
        "tenant_id": tenant,
        "user_id": demo_id("admin"),
        "agent_id": _AGENT,
        "active_run_id": _RUN,
        "plan": {},
        "loaded_skills": [],
    }
    service.runs[_RUN] = {
        "id": _RUN,
        "tenant_id": tenant,
        "agent_id": _AGENT,
        "user_id": demo_id("admin"),
        "conversation_id": _AGENT,
        "input_message_id": _USER,
        "callback_url": "https://example.test/hook",
        "result_summary": "done",
        "error": {"code": "none"},
        "usage": {},
        "budget": {},
        "trigger": "routine",
    }
    service.messages[_USER] = {
        "id": _USER,
        "tenant_id": tenant,
        "conversation_id": _AGENT,
        "run_id": _RUN,
        "text": "Prepare the weekly digest.",
        "content": [{"type": "text", "text": "Prepare the weekly digest."}],
    }
    service.events[_RUN] = [
        {
            "seq": 1,
            "type": "run.completed",
            "run_id": str(_RUN),
            "tenant_id": str(tenant),
            "data": {"status": "completed"},
            "ts": now,
        }
    ]
    service.agents["skip"] = {"slug": "missing-id"}  # type: ignore[index]
    mark_all_dirty(service)


def test_codec_accepts_only_real_values() -> None:
    now = datetime.now(UTC)
    assert as_uuid(uuid.uuid4()) is not None
    assert as_uuid(str(uuid.uuid4())) is not None
    assert as_uuid("nope") is None
    assert as_uuid("") is None
    assert as_uuid(1) is None
    assert as_text(None, "d") == "d"
    assert as_text(3) == "3"
    assert as_int(True, 4) == 4
    assert as_int("x", 4) == 4
    assert as_int(2) == 2
    assert as_bool(0) is False
    assert as_dt(now) == now
    assert as_dt("now") is None
    assert as_json({"a": 1}, {}) == '{"a":1}'
    assert as_json("x", []) == "[]"
    assert as_vector([1] * 3) is None
    assert as_vector([True] + [0] * 1023) is None
    assert as_vector([0] * 1024) is not None
    assert row_dict("x") == {}
    assert row_dict({"a": 1}) == {"a": 1}


def test_tracking_records_every_mutation() -> None:
    bucket = TrackedDict(SimpleNamespace(reloading=False), "skills")
    bucket["row"] = {"name": "brief", "tags": ["weekly"]}
    row = bucket["row"]
    assert isinstance(row, dict)
    row["name"] = "digest"
    tags = row["tags"]
    assert isinstance(tags, TrackedList)
    tags.append("monday")
    tags.extend(["friday"])
    tags[0] = "sunday"
    tags[0:1] = ["monday"]
    assert tags.pop() == "friday"
    bucket["plain"] = "text"
    del bucket["plain"]
    assert bucket.pop("missing", None) is None
    bucket.store.reloading = True
    before = set(bucket.dirty)
    bucket.touch("row")
    assert bucket.dirty == before
    service = ChatService()
    service.document_chunks = []  # type: ignore[assignment]
    install_tracking(service)
    install_tracking(service)
    assert isinstance(service.skills, TrackedDict)


@pytest.mark.asyncio
async def test_flush_writes_each_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    _Session.raise_once = True
    engine = _patch_engines(monkeypatch)
    service = ChatService()
    _seed(service)
    service.durable_engine = engine
    await flush_store(service)
    service._flushing = True
    await flush_store(service)
    assert service._flush_again is True
    await flush_store(SimpleNamespace())
    ran = event_tenant(service, _RUN)
    assert ran is None
    event_tenant(SimpleNamespace(), _RUN)


def test_schedule_flush_queues_one_task(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_engines(monkeypatch)
    idle = SimpleNamespace(durable_engine=None)
    schedule_flush(idle)
    store = SimpleNamespace(durable_engine=_Engine(), _flush_again=False)

    async def _run() -> None:
        waiting = asyncio.create_task(asyncio.sleep(30))
        store._flush_task = waiting
        schedule_flush(store)
        assert store._flush_again is True
        waiting.cancel()
        store.durable_engine = None
        schedule_flush(store)

    asyncio.run(_run())
    schedule_flush(SimpleNamespace(durable_engine=_Engine()))


@pytest.mark.asyncio
async def test_hydrate_and_reload_merge_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _Session.raise_once = False
    engine = _patch_engines(monkeypatch)
    service = ChatService()
    install_tracking(service)
    service.durable_engine = engine
    service.durable = True
    await hydrate_tenant(service, engine, _TENANT)  # type: ignore[arg-type]
    assert service.agents[_AGENT]["slug"] == "assistant"
    await reload_run(service, _RUN)
    assert service.messages
    await reload_document(service, _DOC)
    assert service.knowledge_documents[_DOC]["title"] == "Handbook"
    _Session.raise_once = False

    class _Empty(_Session):
        async def execute(self, statement: object, params: object = None) -> _Rows:
            del statement, params
            return _Rows([])

    monkeypatch.setattr(hydrate_mod, "AsyncSession", _Empty)
    await reload_run(service, uuid.uuid4())
    await reload_document(service, uuid.uuid4())
    await reload_run(SimpleNamespace(), _RUN)


def test_bind_remaps_dev_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_DURABLE_STATE", "memory")
    assert should_bind() is False
    monkeypatch.setenv("AR_DURABLE_STATE", "postgres")
    assert should_bind() is True
    monkeypatch.delenv("AR_DURABLE_STATE", raising=False)
    assert should_bind() is False
    tenant = uuid.uuid4()
    admin = uuid.uuid4()
    same = demo_id("builder")
    users = {
        "admin@dev.local": admin,
        "builder@dev.local": same,
        "member@dev.local": uuid.uuid4(),
        "approver@dev.local": uuid.uuid4(),
    }
    mapping = _id_map(tenant, users)
    assert mapping[demo_id("tenant")] == tenant
    assert demo_id("builder") not in mapping
    service = ChatService()
    service.agents[demo_id("assistant")] = {
        "id": demo_id("assistant"),
        "slug": "assistant",
        "owner_user_id": demo_id("admin"),
        "tags": [demo_id("admin")],
    }
    _remap(service, {})
    _remap(service, {demo_id("admin"): admin, demo_id("assistant"): _AGENT})
    assert service.agents[_AGENT]["owner_user_id"] == admin
    binding = DevBinding(tenant_id=tenant, users=users)
    assert user_for_email(None, "admin@dev.local") is None
    assert user_for_email(binding, "Admin@dev.local") == admin
    assert binding_from(SimpleNamespace()) is None
    assert binding_from(SimpleNamespace(dev_binding=binding)) == binding


@pytest.mark.asyncio
async def test_bind_connects_and_waits_for_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bind_mod, "create_async_engine", lambda *_a, **_k: _Engine())
    engine = await _connect("postgresql+asyncpg://ar:ar@127.0.0.1:1/none")
    assert isinstance(engine, _Engine)

    class _Down(_Engine):
        def connect(self) -> _Conn:
            raise RuntimeError("down")

    monkeypatch.setattr(bind_mod, "create_async_engine", lambda *_a, **_k: _Down())
    assert await _connect("postgresql+asyncpg://ar:ar@127.0.0.1:1/none") is None

    class _Lookup(_Session):
        tenant: ClassVar[uuid.UUID | None] = _TENANT
        users: ClassVar[list[tuple[Any, ...]]] = [(_USER, "admin@dev.local")]

        async def scalar(self, *_args: object, **_kwargs: object) -> uuid.UUID | None:
            return _Lookup.tenant

        async def execute(self, statement: object, params: object = None) -> _Rows:
            del statement, params
            return _Rows(_Lookup.users)

    monkeypatch.setattr(bind_mod, "AsyncSession", _Lookup)
    assert await _lookup(_Engine()) == (_TENANT, {"admin@dev.local": _USER})  # type: ignore[arg-type]
    _Lookup.tenant = None
    assert await _lookup(_Engine()) is None  # type: ignore[arg-type]
    _Lookup.tenant = _TENANT
    _Lookup.users = []
    assert await _lookup(_Engine()) is None  # type: ignore[arg-type]

    published = uuid.uuid4()
    _Lookup.users = [(_AGENT, "assistant", published)]

    service = ChatService()
    service.agents[demo_id("assistant")] = {
        "id": demo_id("assistant"),
        "slug": "assistant",
        "published_version_id": demo_id("version"),
    }
    service.versions[demo_id("version")] = {"id": demo_id("version")}
    await _remap_agents(service, _Engine(), _TENANT)  # type: ignore[arg-type]
    assert service.agents[_AGENT]["slug"] == "assistant"

    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(bind_mod, "flush_store", _noop)
    monkeypatch.setattr(bind_mod, "hydrate_tenant", _noop)
    monkeypatch.setattr(bind_mod, "_remap_agents", _noop)
    _Lookup.tenant = None
    monkeypatch.setattr(bind_mod, "create_async_engine", lambda *_a, **_k: _Engine())
    missed = await bind_store(service, "postgresql+asyncpg://unused")
    assert missed is None
    assert getattr(service, "dev_binding", None) is None


@pytest.mark.asyncio
async def test_bind_store_hydrates_when_the_seed_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()

    async def _ready(_url: str) -> _Engine:
        return engine

    async def _found(_engine: object) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
        return _TENANT, {"admin@dev.local": _USER}

    async def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(bind_mod, "_connect", _ready)
    monkeypatch.setattr(bind_mod, "_lookup", _found)
    monkeypatch.setattr(bind_mod, "_remap_agents", _noop)
    monkeypatch.setattr(bind_mod, "flush_store", _noop)
    monkeypatch.setattr(bind_mod, "hydrate_tenant", _noop)
    service = ChatService()
    binding = await bind_store(service, "postgresql+asyncpg://unused")
    assert binding is not None
    assert binding.tenant_id == _TENANT
    assert service.durable is True
    assert service.dev_binding == binding


@pytest.mark.asyncio
async def test_ingest_uses_the_worker_when_temporal_is_up(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatService()
    missing = uuid.uuid4()
    assert ingest_document(service, missing, b"") == "missing"
    assert await ingest_or_enqueue(service, missing, b"x" * (WORKFLOW_MAX_BYTES + 1)) == "missing"
    service._ingest_worker = True
    service.temporal_client = object()
    assert await ingest_or_enqueue(service, missing, b"hi") == "missing"

    started: dict[str, object] = {}

    class _Handle:
        def __init__(self, hang: bool) -> None:
            self.hang = hang

        async def result(self) -> str:
            if self.hang:
                await asyncio.sleep(30)
            return "indexed"

    class _Client:
        def __init__(self, hang: bool = False) -> None:
            self.hang = hang

        async def start_workflow(self, *_args: object, **kwargs: object) -> _Handle:
            started.update(kwargs)
            return _Handle(self.hang)

    service._ingest_worker = False
    service.temporal_client = _Client()

    async def _flushed(_store: object) -> None:
        return None

    async def _reloaded(_store: object, document_id: uuid.UUID) -> None:
        service.knowledge_documents[document_id] = {"id": document_id, "status": "indexed"}

    monkeypatch.setattr("ar_domain.durable.flush.flush_store", _flushed)
    monkeypatch.setattr("ar_domain.durable.hydrate.reload_document", _reloaded)
    assert await ingest_or_enqueue(service, _DOC, b"# week") == "indexed"
    assert started["task_queue"] == "ar-ingest"

    service.temporal_client = _Client(hang=True)

    async def _timeout(*args: object, **_kwargs: object) -> None:
        awaitable = args[0] if args else None
        close = getattr(awaitable, "close", None)
        if close is not None:
            close()
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", _timeout)
    assert await ingest_or_enqueue(service, missing, b"late") == "missing"
    await _delete_stored_chunks(service, _DOC)

    class _Delete:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Delete:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        def begin(self) -> _Delete:
            return self

        async def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

    service.durable_engine = object()
    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession", _Delete)
    await _delete_stored_chunks(service, _DOC)


def test_active_index_uses_pgvector_when_bound() -> None:
    holder = SimpleNamespace(durable=False, durable_engine=None, pg_index=None)
    assert active_index(holder) is not None
    cached = object()
    bound = SimpleNamespace(durable=True, durable_engine=object(), pg_index=cached)
    assert active_index(bound) is cached
    fresh = SimpleNamespace(durable=True, durable_engine=object(), pg_index=None)
    created = active_index(fresh)
    assert fresh.pg_index is created


@pytest.mark.asyncio
async def test_workers_poll_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_ingest.worker import _prepare_store as prepare_ingest
    from ar_ingest.worker import run_worker as run_ingest
    from ar_runtime.worker import _address as runtime_address
    from ar_runtime.worker import _prepare_store as prepare_runtime
    from ar_runtime.worker import run_worker as run_runtime

    class _Worker:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def run(self) -> None:
            raise asyncio.CancelledError

    async def _up(*_args: object, **_kwargs: object) -> object:
        return object()

    async def _down(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("temporal is down")

    async def _stop(_seconds: float) -> None:
        raise asyncio.CancelledError

    async def _bound(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("ar_domain.durable.bind.bind_store", _bound)
    await prepare_runtime()
    await prepare_ingest()
    from ar_ingest.activities import bind_store as bind_ingest
    from ar_runtime.activities.expire_approval import bind_store as bind_runtime

    bind_runtime(None)
    bind_ingest(None)
    monkeypatch.setattr(
        "ar_runtime.worker.get_settings",
        lambda: SimpleNamespace(temporal_address="temporal:7233", database_url="x"),
    )
    assert runtime_address() == "temporal:7233"

    monkeypatch.setattr("ar_runtime.worker.Client.connect", _up)
    monkeypatch.setattr("ar_runtime.worker.Worker", _Worker)
    monkeypatch.setattr("ar_runtime.worker._prepare_store", _bound)
    with pytest.raises(asyncio.CancelledError):
        await run_runtime()

    monkeypatch.setattr("ar_ingest.worker.Client.connect", _up)
    monkeypatch.setattr("ar_ingest.worker.Worker", _Worker)
    monkeypatch.setattr("ar_ingest.worker._prepare_store", _bound)
    with pytest.raises(asyncio.CancelledError):
        await run_ingest()

    monkeypatch.setattr("ar_runtime.worker.Client.connect", _down)
    monkeypatch.setattr("ar_runtime.worker.asyncio.sleep", _stop)
    with pytest.raises(asyncio.CancelledError):
        await run_runtime()

    monkeypatch.setattr("temporalio.client.Client.connect", _up)
    monkeypatch.setattr("temporalio.worker.Worker", _Worker)
    from ar_system.worker import run_worker as run_system

    with pytest.raises(asyncio.CancelledError):
        await run_system()


@pytest.mark.asyncio
async def test_worker_mains_serve_health(monkeypatch: pytest.MonkeyPatch) -> None:
    import ar_ingest.main as ingest_main
    import ar_runtime.main as runtime_main
    import ar_system.main as system_main

    class _Server:
        def __init__(self, _config: object) -> None:
            return None

        async def serve(self) -> None:
            return None

    async def _client(_address: str) -> object:
        return object()

    for module in (runtime_main, ingest_main, system_main):
        monkeypatch.setattr(module.uvicorn, "Server", _Server)
        monkeypatch.setattr(module.temporalio.client.Client, "connect", _client)
        monkeypatch.setattr(module.asyncio, "run", lambda coro: coro.close())
        await module._serve(asyncio.sleep(0))
        assert await module.connect_temporal("localhost:7233") is not None
        module.main()


@pytest.mark.asyncio
async def test_durable_middleware_binds_once(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_api.middleware.durable import DurableMiddleware

    binding = DevBinding(tenant_id=_TENANT, users={"admin@dev.local": _USER})
    calls = {"bind": 0, "flush": 0}

    async def _bind(_chat: object, _url: str) -> DevBinding:
        calls["bind"] += 1
        return binding

    async def _flush(_chat: object) -> None:
        calls["flush"] += 1

    async def _connect(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("temporal is down")

    monkeypatch.setattr("ar_domain.durable.bind.should_bind", lambda: True)
    monkeypatch.setattr("ar_domain.durable.bind.bind_store", _bind)
    monkeypatch.setattr("ar_domain.durable.flush.flush_store", _flush)
    monkeypatch.setattr("temporalio.client.Client.connect", _connect)

    class _App:
        def __init__(self) -> None:
            self.state = SimpleNamespace(
                chat=SimpleNamespace(
                    _bind_attempted=False,
                    durable_engine=None,
                    model_gateway_url="",
                ),
                settings=SimpleNamespace(
                    model_gateway_url="http://gateway",
                    database_url="postgresql://unused",
                    temporal_address="",
                ),
            )

    app = _App()

    async def _downstream(_scope: object, _receive: object, _send: object) -> None:
        return None

    middleware = DurableMiddleware(_downstream)
    await middleware({"type": "lifespan", "app": app}, None, None)  # type: ignore[arg-type]
    scope = {"type": "http", "app": app}
    await middleware(scope, None, None)  # type: ignore[arg-type]
    assert calls["bind"] == 1
    assert app.state.chat.model_gateway_url == "http://gateway"
    app.state.chat.durable_engine = object()
    await middleware(scope, None, None)  # type: ignore[arg-type]
    assert calls["flush"] == 1
    assert calls["bind"] == 1


@pytest.mark.asyncio
async def test_execute_chat_turn_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_runtime.activities import execute_chat_turn as turn

    run_id = uuid.uuid4()

    class _Store:
        def __init__(self) -> None:
            self.runs = {run_id: {"status": "completed"}}

        async def generate(self, *_args: object) -> None:
            return None

    store = _Store()

    async def _reload(*_args: object) -> None:
        return None

    async def _flush(*_args: object) -> None:
        return None

    monkeypatch.setattr(turn, "current_store", lambda: store)
    monkeypatch.setattr("ar_domain.durable.hydrate.reload_run", _reload)
    monkeypatch.setattr("ar_domain.durable.flush.flush_store", _flush)
    result = await turn.execute_chat_turn({"run_id": str(run_id), "text": "digest", "names": [1]})
    assert result["status"] == "completed"
    monkeypatch.setattr(turn, "current_store", lambda: None)
    missing = await turn.execute_chat_turn({"run_id": str(run_id)})
    assert missing["status"] == "missing_store"


def test_gateway_echoes_when_fake_llm_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    from fastapi.testclient import TestClient

    from ar_model_gateway.main import create_application

    class _Response:
        def __init__(self, body: object, status_code: int = 200) -> None:
            self._body = body
            self.status_code = status_code

        def json(self) -> object:
            return self._body

    class _Client:
        mode = "down"

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

        async def post(self, *_args: object, **_kwargs: object) -> _Response:
            if _Client.mode == "down":
                raise httpx.ConnectError("down")
            if _Client.mode == "bad":
                return _Response(["nope"])
            return _Response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    client = TestClient(create_application())
    echoed = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "week"}]},
        headers={"x-fake-script-set": "digest"},
    )
    assert echoed.status_code == 200
    assert echoed.json()["choices"][0]["message"]["content"] == "fake: week"
    _Client.mode = "bad"
    fallback = client.post("/v1/chat/completions", json={"messages": []})
    assert "fake:" in fallback.json()["choices"][0]["message"]["content"]
    _Client.mode = "ok"
    forwarded = client.post("/v1/chat/completions", json={"messages": []})
    assert forwarded.json()["choices"][0]["message"]["content"] == "ok"

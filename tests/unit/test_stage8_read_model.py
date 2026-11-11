"""Stage 8 read model. Proof label: unit (in-process, no network, no model).

The contract case that uses Postgres is ``test_stage8_read_model_contract``.
"""

from __future__ import annotations

import ast
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ar_common.settings import BaseServiceSettings, EnvName, get_settings, set_settings
from ar_domain.audit.read import verify_public_chain
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.bind import SchemaNotReadyError, TenantBinding, TenantNotReadyError
from ar_domain.readmodel.activity import payload_uuid, repository_activity
from ar_domain.readmodel.audit import chain_candidates, seal_latest
from ar_domain.readmodel.boot import MemoryStoreRefusedError, build_product_store
from ar_domain.readmodel.model import RepositoryReadModel, apply_tenant_context
from ar_mcp_gateway.main import create_application
from ar_testing.demo_tenant import seed_demo_tenant

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_VERSIONS = _ROOT / "libs/ar_domain/src/ar_domain/migrations/versions"
_SECRET = SecretStr("unit-test-cursor-secret")


def _prod_settings() -> BaseServiceSettings:
    return BaseServiceSettings(
        _env_file=None,
        env=EnvName.PROD,
        cursor_secret=_SECRET,
    )


def test_production_boot_refuses_the_memory_double() -> None:
    previous = get_settings()
    set_settings(_prod_settings())
    try:
        with pytest.raises(MemoryStoreRefusedError):
            ChatService()
        store = build_product_store(
            _prod_settings(), allow_loopback=False, fake_models_allowed=False
        )
    finally:
        set_settings(previous)
    assert isinstance(store, RepositoryReadModel)
    assert not isinstance(store, ChatService)
    assert store.holds_tenant_state() is False
    other = build_product_store(_prod_settings(), allow_loopback=False)
    assert other is not store
    assert other.holds_tenant_state() is False


def test_dev_boot_keeps_the_memory_double() -> None:
    settings = BaseServiceSettings(_env_file=None, env=EnvName.DEV)
    store = build_product_store(settings, allow_loopback=True, fake_models_allowed=True)
    assert isinstance(store, ChatService)


def test_gateway_audit_joins_the_chain_the_verifier_checks() -> None:
    app = create_application()
    seed_demo_tenant(app.state.chat)
    store = app.state.chat
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    server = store.tool_server_versions[version["tool_server_version_id"]]
    server["endpoint_url"] = "https://blocked.example/mcp"
    client = TestClient(app)
    called = client.post(
        "/internal/v1/tool-calls:execute",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "arguments": {},
            "modelCallId": "remote",
        },
    )
    assert called.status_code == 200, called.text
    chain = list(store.audit_chain)
    assert chain_candidates(store.audit_log)
    assert any(
        row.get("action") == "tool.denied" and row.get("detail", {}).get("via") == "gateway"
        for row in chain
    )
    report = verify_public_chain(chain)
    assert report["ok"] is True
    assert report["checked"] == len(chain)
    tampered = dict(chain[-1])
    tampered["action"] = "tool.called"
    broken = verify_public_chain([*chain[:-1], tampered])
    assert broken["ok"] is False


def test_single_alembic_head_is_stage5_revision() -> None:
    revisions: dict[str, str | None] = {}
    for path in _VERSIONS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        revision: str | None = None
        down: str | None = None
        for node in tree.body:
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            if node.target.id == "revision" and isinstance(node.value.value, str):
                revision = node.value.value
            if node.target.id == "down_revision":
                down = node.value.value if isinstance(node.value.value, str) else None
        if revision is not None:
            revisions[revision] = down
    pointed = {item for item in revisions.values() if item}
    heads = sorted(rev for rev in revisions if rev not in pointed)
    assert heads == ["0042"]


class _Result:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows

    def first(self) -> object:
        return self._rows[0] if self._rows else None


class _Connection:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    async def __aenter__(self) -> _Connection:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def execute(self, _statement: object, _params: object = None) -> _Result:
        return _Result(self.rows)


class _Engine:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def connect(self) -> _Connection:
        return _Connection(self.rows)


class _Session:
    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    def begin(self) -> _Session:
        return self

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        return None


def _model() -> RepositoryReadModel:
    model = RepositoryReadModel(database_url="postgresql+asyncpg://unused/db", allow_loopback=True)
    model.event_bus = object()
    model.sse_gate = object()

    async def engine() -> _Engine:
        return _Engine([])

    model.engine_for = engine  # type: ignore[method-assign]
    return model


async def test_read_model_resolves_tenants_and_commits_a_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = uuid.uuid4()
    model = _model()
    model.engine_for = lambda: _async_engine([(tenant,)])  # type: ignore[method-assign]
    assert await model.tenant_ids() == [tenant]
    binding = TenantBinding(tenant, "acme", "Acme", "team", {})

    async def lookup(_engine: object, slug: str) -> TenantBinding:
        assert slug == "acme"
        return binding

    monkeypatch.setattr("ar_domain.durable.bind._lookup", lookup)
    assert await model.lookup_tenant(" acme ") == binding

    async def unbound(_engine: object, _slug: str) -> object:
        return object()

    monkeypatch.setattr("ar_domain.durable.bind._lookup", unbound)
    with pytest.raises(TypeError):
        await model.lookup_tenant("acme")
    monkeypatch.setattr("ar_domain.durable.bind._lookup", lookup)
    assert await model.resolve_tenant({"tenant_id": str(tenant)}) == tenant
    assert await model.resolve_tenant({"tenant_id": tenant}) == tenant
    assert await model.resolve_tenant(str(tenant)) == tenant
    assert await model.resolve_tenant("not-a-uuid") is None
    assert await model.resolve_tenant(1) is None
    assert await model._tenant_of("missing", tenant) is None
    model.engine_for = lambda: _async_engine([(None,)])  # type: ignore[method-assign]
    assert await model._tenant_of("runs", tenant) is None
    model.engine_for = _raising_engine  # type: ignore[method-assign]
    assert await model._tenant_of("runs", tenant) is None
    model.engine_for = lambda: _async_engine([(str(tenant),)])  # type: ignore[method-assign]
    found = await model.resolve_tenant({"run_id": str(uuid.uuid4()), "nope": "x"})
    assert found == tenant
    found = await model.resolve_tenant({"run_id": "not-a-uuid", "routine_id": str(uuid.uuid4())})
    assert found == tenant
    model.engine_for = lambda: _async_engine([(None,)])  # type: ignore[method-assign]
    assert (
        await model.resolve_tenant({"run_id": str(uuid.uuid4()), "routine_id": str(uuid.uuid4())})
        is None
    )
    flushed: list[object] = []

    async def hydrate(*_args: object, **_kwargs: object) -> None:
        return None

    async def flush(store: object) -> None:
        flushed.append(store)

    monkeypatch.setattr("ar_domain.readmodel.model.AsyncSession", lambda *_a, **_k: _Session())
    monkeypatch.setattr("ar_domain.durable.hydrate.hydrate_tenant", hydrate)
    monkeypatch.setattr("ar_domain.durable.flush.flush_store", flush)
    from ar_domain.durable import tracking

    monkeypatch.setattr(tracking, "BUCKETS", (*tracking.BUCKETS, "not_a_bucket"))
    del model.pod_creator
    model.engine_for = lambda: _async_engine([])  # type: ignore[method-assign]
    async with model.open(tenant, user_id="user", request_id="req") as unit:
        assert unit.context_tenant_id == tenant
        assert unit.event_bus is model.event_bus
        unit.conversations[uuid.uuid4()] = {"id": "row"}
    assert flushed and flushed[0] is unit


def _async_engine(rows: list[object]) -> _Engine:
    async def engine() -> _Engine:
        return _Engine(rows)

    return engine()  # type: ignore[return-value]


def _raising_engine() -> object:
    class _Boom:
        def connect(self) -> object:
            raise RuntimeError("missing table")

    async def engine() -> _Boom:
        return _Boom()

    return engine()  # type: ignore[return-value]


async def test_wait_ready_retries_then_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    model = RepositoryReadModel(database_url="postgresql+asyncpg://unused/db")
    calls = {"n": 0}

    async def engine() -> object:
        return object()

    async def lookup(_engine: object, _slug: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise SchemaNotReadyError
        if calls["n"] == 2:
            raise ConnectionError("down")
        if calls["n"] == 3:
            raise RuntimeError("still down")
        return

    monkeypatch.setattr(model, "engine_for", engine)
    monkeypatch.setattr("ar_domain.durable.bind._lookup", lookup)

    async def pause(_seconds: float) -> None:
        return None

    from ar_testing.sleeping import in_this_thread

    monkeypatch.setattr("ar_domain.readmodel.model.asyncio.sleep", in_this_thread(pause))
    await model.wait_ready(retry_s=0)
    assert calls["n"] == 4


async def test_engine_for_builds_one_when_connect_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    model = RepositoryReadModel(database_url="postgresql+asyncpg://unused/db")
    built = object()

    async def connect(_url: str) -> None:
        return None

    monkeypatch.setattr("ar_domain.durable.bind._connect", connect)
    monkeypatch.setattr("sqlalchemy.ext.asyncio.create_async_engine", lambda *_a, **_k: built)
    assert await model.engine_for() is built
    assert model.engine is built

    async def connect_ready(_url: str) -> object:
        return built

    fresh = RepositoryReadModel(database_url="postgresql+asyncpg://unused/db")
    monkeypatch.setattr("ar_domain.durable.bind._connect", connect_ready)
    assert await fresh.engine_for() is built
    import sqlalchemy.ext.asyncio as sa_asyncio

    monkeypatch.undo()
    ready = sa_asyncio.create_async_engine("postgresql+asyncpg://unused/db")
    fresh.engine = ready
    assert await fresh.engine_for() is ready
    await ready.dispose()


def test_seal_skips_a_request_unit_and_an_unknown_action() -> None:
    scoped = SimpleNamespace(request_scoped=True, audit_log=[{"action": "tool.called"}])
    seal_latest(scoped)
    assert not hasattr(scoped, "audit_chain")
    empty = SimpleNamespace(audit_log=[])
    seal_latest(empty)
    unknown = SimpleNamespace(
        audit_log=[{"action": "not.a.real.action", "tenant_id": str(uuid.uuid4())}]
    )
    seal_latest(unknown)
    assert chain_candidates(["nope", {"action": "tool.called"}]) == []


async def test_activity_wrapper_uses_the_unit_then_the_double() -> None:
    from ar_runtime.activities.expire_approval import bind_store, current_store

    tenant = uuid.uuid4()
    model = _model()

    async def resolve(payload: object) -> uuid.UUID | None:
        if isinstance(payload, dict) and payload.get("skip"):
            return None
        return tenant

    @asynccontextmanager
    async def opened(tenant_id: uuid.UUID, **_kwargs: object) -> object:
        yield SimpleNamespace(tenant_id=tenant_id, request_scoped=True)

    model.resolve_tenant = resolve  # type: ignore[method-assign]
    model.open = opened  # type: ignore[method-assign]
    previous = current_store()
    bind_store(model)

    async def work(payload: dict[str, object]) -> object:
        return current_store()

    wrapped = repository_activity(lambda: model)(work)
    try:
        unit = await wrapped({})
        assert unit.tenant_id == tenant
        assert await wrapped({"skip": True}) is model
        assert payload_uuid({"run_id": str(tenant)}, "run_id") == tenant
        assert payload_uuid({"run_id": tenant}, "run_id") == tenant
        assert payload_uuid({"run_id": "not-a-uuid"}, "run_id") is None
        assert payload_uuid({"run_id": ""}, "run_id") is None
        assert payload_uuid("nope", "run_id") is None
    finally:
        bind_store(previous)


async def test_sse_gate_counts_in_the_shared_client() -> None:
    from ar_api.sse_gate import ValkeySseGate

    class _Client:
        def __init__(self) -> None:
            self.count = 0

        async def incr(self, _key: str) -> int:
            self.count += 1
            return self.count

        async def decr(self, _key: str) -> int:
            self.count -= 1
            return self.count

        async def expire(self, _key: str, _seconds: int) -> bool:
            return True

        async def set(self, _key: str, value: str, ex: int | None = None) -> bool:
            del ex
            self.count = int(value)
            return True

    gate = ValkeySseGate("redis://unused", client=_Client())
    assert await gate.acquire("user", 1) is True
    assert await gate.acquire("user", 1) is False
    await gate.release("user")
    gate._client.count = 0  # type: ignore[attr-defined]
    await gate.release("user")


async def test_middleware_opens_one_unit_per_request() -> None:
    from ar_api.middleware.read_model import ReadModelMiddleware

    tenant = uuid.uuid4()
    model = _model()
    seen: list[object] = []

    @asynccontextmanager
    async def opened(tenant_id: uuid.UUID, **kwargs: object) -> object:
        yield SimpleNamespace(tenant_id=tenant_id, user=kwargs.get("user_id"))

    model.open = opened  # type: ignore[method-assign]

    class _App:
        def __init__(self) -> None:
            self.state = SimpleNamespace(chat=model)

    async def inner(scope: dict[str, object], _receive: object, _send: object) -> None:
        state = scope["state"]
        unit = state.get("read_unit") if isinstance(state, dict) else None
        if unit is not None:
            seen.append(unit.tenant_id)

    middleware = ReadModelMiddleware(inner)
    app = _App()
    scope = {
        "type": "http",
        "path": "/api/v1/conversations",
        "app": app,
        "state": {
            "principal": SimpleNamespace(tenant_id=tenant, id="user"),
            "request_id": "req",
        },
    }
    await middleware(scope, None, None)
    assert seen == [tenant]
    assert scope["state"]["read_unit"] is None  # type: ignore[index]
    scope["path"] = "/healthz"
    await middleware(scope, None, None)
    scope["path"] = "/api/v1/conversations"
    scope["state"] = {}  # type: ignore[index]
    await middleware(scope, None, None)
    assert seen == [tenant]


async def test_login_binding_reads_postgres_and_ignores_a_missing_tenant() -> None:
    from ar_api.auth.identity import _as_engine, _login_binding, _otp_matches, _remember_person

    tenant = uuid.uuid4()
    binding = TenantBinding(tenant, "acme", "Acme", "team", {})
    model = _model()

    async def lookup(_slug: str) -> TenantBinding:
        return binding

    async def engine() -> object:
        return SimpleNamespace(connect=lambda: None)

    model.lookup_tenant = lookup  # type: ignore[method-assign]
    model.engine_for = engine  # type: ignore[method-assign]
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(chat=model)))
    _store, found, attached = await _login_binding(request)  # type: ignore[arg-type]
    assert found == binding
    assert attached is not None

    async def missing(_slug: str) -> None:
        raise TenantNotReadyError

    model.lookup_tenant = missing  # type: ignore[method-assign]
    assert (await _login_binding(request))[1] is None  # type: ignore[arg-type]

    async def boom(_slug: str) -> None:
        raise SchemaNotReadyError

    model.lookup_tenant = boom  # type: ignore[method-assign]
    assert (await _login_binding(request))[1] is None  # type: ignore[arg-type]

    async def unexpected(_slug: str) -> None:
        raise RuntimeError("down")

    model.lookup_tenant = unexpected  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        await _login_binding(request)  # type: ignore[arg-type]

    async def plain(_slug: str) -> object:
        return object()

    model.lookup_tenant = plain  # type: ignore[method-assign]
    assert (await _login_binding(request))[1] is None  # type: ignore[arg-type]
    assert _otp_matches("%%%", "123456") is False
    memory = ChatService()
    memory.durable_engine = SimpleNamespace(connect=lambda: None)  # type: ignore[assignment]
    request.app.state.chat = memory
    assert _as_engine(None) is None
    assert _as_engine(object()) is None
    assert (await _login_binding(request))[2] is not None  # type: ignore[arg-type]
    user = SimpleNamespace(id=uuid.uuid4(), display_name="Ada", email="Ada@x", status="active")
    _remember_person(memory, user, ["admin"])
    _remember_person(object(), user, "nope")
    assert memory.user_roles[user.id] == {"admin"}


async def test_reaper_and_reconcile_walk_each_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_system.routines_store import bind_store as bind_routines
    from ar_system.routines_store import current_store
    from ar_system.workflows.routine_run import reconcile_activity
    from ar_system.workflows.sandbox_reaper import reap_sandboxes

    tenant = uuid.uuid4()
    model = _model()

    async def tenants() -> list[uuid.UUID]:
        return [tenant]

    @asynccontextmanager
    async def opened(tenant_id: uuid.UUID, **_kwargs: object) -> object:
        yield SimpleNamespace(tenant_id=tenant_id)

    model.tenant_ids = tenants  # type: ignore[method-assign]
    model.open = opened  # type: ignore[method-assign]
    monkeypatch.setattr(
        "ar_domain.sandboxes.runtime.reap", lambda _store: {"suspended": 1, "terminated": 0}
    )
    monkeypatch.setattr("ar_system.workflows.sandbox_reaper._STORE", model)
    assert await reap_sandboxes() == {"suspended": 1, "terminated": 0}
    monkeypatch.setattr(
        "ar_system.workflows.routine_run.reconcile_schedules", lambda _store: {"repaired": 2}
    )
    previous = None
    try:
        previous = current_store()
    except RuntimeError:
        previous = None
    bind_routines(model)
    try:
        assert await reconcile_activity() == {"repaired": 2}
    finally:
        if previous is not None:
            bind_routines(previous)


def test_waiting_runs_cancel_and_accept_input() -> None:
    """The waiting-run branches stay covered when the read model reuses them."""
    store = ChatService()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    conversation = uuid.uuid4()
    store.conversations[conversation] = {
        "id": conversation,
        "tenant_id": tenant,
        "user_id": user,
        "active_run_id": None,
    }
    waiting = uuid.uuid4()
    store.runs[waiting] = {
        "id": waiting,
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation,
        "status": "waiting_input",
        "assistant_message_id": None,
    }
    store.conversations[conversation]["active_run_id"] = waiting
    cancelled = store.cancel_run(tenant, user, waiting)
    assert cancelled["status"] == "cancelled"
    approval = uuid.uuid4()
    store.runs[approval] = {
        "id": approval,
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation,
        "status": "waiting_approval",
        "pending_approval": {},
    }
    assert store.cancel_run(tenant, user, approval)["status"] == "waiting_approval"
    running = uuid.uuid4()
    store.runs[running] = {
        "id": running,
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation,
        "status": "running",
    }
    assert store.cancel_run(tenant, user, running)["status"] == "running"
    assert running in store.cancel_flags
    answered = uuid.uuid4()
    message = uuid.uuid4()
    store.messages[message] = {
        "id": message,
        "tenant_id": tenant,
        "text": "",
        "status": "streaming",
    }
    store.runs[answered] = {
        "id": answered,
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation,
        "status": "waiting_input",
        "assistant_message_id": message,
    }
    store.conversations[conversation]["active_run_id"] = answered
    done = store.submit_input(tenant, user, answered, "  thanks  ")
    assert done["status"] == "completed"
    assert store.messages[message]["text"] == "thanks"


async def test_finish_grounded_records_the_answer() -> None:
    store = ChatService()

    async def remember(
        _self: ChatService, _run: dict[str, object], _user_text: str, _answer: str
    ) -> None:
        return None

    store._remember = remember.__get__(store, ChatService)  # type: ignore[method-assign]
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    conversation_id = uuid.uuid4()
    message_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    store.messages[message_id] = {"id": message_id, "text": "question", "role": "user"}
    assistant = {"id": assistant_id, "text": "", "status": "streaming", "content": []}
    store.messages[assistant_id] = assistant
    conversation = {"id": conversation_id, "tenant_id": tenant, "active_run_id": run_id}
    run = {
        "id": run_id,
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation_id,
        "input_message_id": message_id,
        "assistant_message_id": assistant_id,
        "status": "running",
    }
    store.runs[run_id] = run
    store.last_remote_usage = {"tokens_in": 3, "tokens_out": 4}
    await store._finish_grounded(
        run,
        assistant,
        conversation,
        {
            "text": "answer",
            "citations": [{"passage_id": "p1"}],
            "report": {"mode": "quote"},
            "parts": [{"type": "text", "text": "answer"}],
        },
    )
    assert run["status"] == "completed"
    assert conversation["active_run_id"] is None
    usage = run["usage"]
    assert isinstance(usage, dict)
    assert usage["tokens_in"] == 3
    assert usage["tokens_out"] == 4


async def test_apply_tenant_context_sets_the_session() -> None:
    seen: dict[str, object] = {}

    class _Db:
        async def execute(self, _statement: object, params: object = None) -> None:
            seen.update(params or {})

    tenant = uuid.uuid4()
    await apply_tenant_context(_Db(), tenant, user_id="user", request_id="req")  # type: ignore[arg-type]
    assert seen["tenant_id"] == str(tenant)
    assert seen["user_id"] == "user"

"""Stage 1 safe process. Proof label: unit (in-process, no network, no model)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError
from temporalio.service import RPCError, RPCStatusCode

from ar_api.auth.session import MemorySessionStore, ValkeySessionStore, new_session
from ar_api.process import install_process_state
from ar_api.ratelimit import ValkeyTokenBucket
from ar_api.readiness import (
    api_readiness,
    ping_postgres,
    ping_temporal,
    ping_valkey,
    readiness_names,
)
from ar_common.errors import UnavailableError
from ar_common.settings import (
    DEV_CURSOR_SECRET,
    BaseServiceSettings,
    EnvName,
    cursor_secret_text,
    get_settings,
    host_exec_allowed,
    set_settings,
    uses_shared_process_state,
)
from ar_domain.chat.service import ChatService
from ar_domain.events.idempotency import StoredResponse
from ar_domain.events.idempotency_pg import PostgresIdempotencyStore, decode_body, encode_body
from ar_domain.runs.event_bus import ValkeyRunBus
from ar_domain.sandboxes.runtime import run_tool
from ar_domain.tools.general import dispatch_general

_SECRET = SecretStr("unit-test-cursor-secret")


def _prod_settings(**overrides: object) -> BaseServiceSettings:
    return BaseServiceSettings(
        _env_file=None,
        env=EnvName.PROD,
        cursor_secret=_SECRET,
        **overrides,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_host_exec_is_dev_and_ci_only() -> None:
    assert host_exec_allowed(BaseServiceSettings(_env_file=None, env=EnvName.DEV))
    assert host_exec_allowed(BaseServiceSettings(_env_file=None, env=EnvName.CI))
    assert not host_exec_allowed(_prod_settings())
    staging = BaseServiceSettings(_env_file=None, env=EnvName.STAGING, cursor_secret=_SECRET)
    assert not host_exec_allowed(staging)


@pytest.mark.unit
def test_shell_and_code_refuse_host_execution_outside_dev() -> None:
    previous = get_settings()
    set_settings(_prod_settings())
    try:
        shell = dispatch_general(SimpleNamespace(), "shell", {"command": "echo hi"})
        code = dispatch_general(SimpleNamespace(), "code", {"source": "print(1)"})
    finally:
        set_settings(previous)
    assert shell["code"] == "sandbox_unavailable"
    assert code["code"] == "sandbox_unavailable"
    assert shell["is_error"] is True


@pytest.mark.unit
def test_empty_endpoint_is_sandbox_unavailable_outside_dev() -> None:
    previous = get_settings()
    set_settings(_prod_settings())
    tenant = uuid.uuid4()
    conversation = uuid.uuid4()
    sandbox_id = uuid.uuid4()
    store = SimpleNamespace(
        sandbox_locks={},
        sandboxes={
            sandbox_id: {
                "id": sandbox_id,
                "tenant_id": tenant,
                "scope_key": f"conv:{conversation}",
                "status": "ready",
                "endpoint_url": None,
            }
        },
        versions={},
        tenant_settings={},
    )
    try:
        result = run_tool(
            store,
            "exec",
            {
                "command": "echo should-not-run",
                "_tenant_id": tenant,
                "_user_id": uuid.uuid4(),
                "_conversation_id": conversation,
            },
        )
    finally:
        set_settings(previous)
    assert result["code"] == "sandbox_unavailable"


@pytest.mark.unit
def test_boot_refuses_the_dev_cursor_secret_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_CURSOR_SECRET", raising=False)
    with pytest.raises(ValidationError):
        BaseServiceSettings(_env_file=None, env=EnvName.PROD)
    with pytest.raises(ValidationError):
        BaseServiceSettings(
            _env_file=None, env=EnvName.PROD, cursor_secret=SecretStr(DEV_CURSOR_SECRET)
        )
    built = _prod_settings()
    assert built.cursor_secret.get_secret_value() == "unit-test-cursor-secret"
    monkeypatch.setenv("AR_ENV", "prod")
    monkeypatch.delenv("AR_CURSOR_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        cursor_secret_text()
    monkeypatch.setenv("AR_CURSOR_SECRET", "unit-test-cursor-secret")
    assert cursor_secret_text() == "unit-test-cursor-secret"


@pytest.mark.unit
def test_shared_process_state_is_outside_dev_and_ci() -> None:
    assert not uses_shared_process_state(EnvName.DEV)
    assert not uses_shared_process_state(EnvName.CI)
    assert uses_shared_process_state(EnvName.PROD)
    assert readiness_names(shared=False, temporal_required=False) == ["postgres"]
    assert readiness_names(shared=True, temporal_required=True) == [
        "postgres",
        "valkey",
        "temporal",
    ]


@pytest.mark.unit
def test_production_wiring_uses_shared_stores() -> None:
    app = SimpleNamespace(state=SimpleNamespace(chat=SimpleNamespace()))
    install_process_state(app, _prod_settings(temporal_required=True), b"k" * 32)  # type: ignore[arg-type]
    assert isinstance(app.state.sessions, ValkeySessionStore)
    assert isinstance(app.state.widget_sessions, ValkeySessionStore)
    assert isinstance(app.state.idempotency, PostgresIdempotencyStore)
    assert isinstance(app.state.chat.event_bus, ValkeyRunBus)
    assert app.state.chat.temporal_required is True
    dev = SimpleNamespace(state=SimpleNamespace(chat=SimpleNamespace(temporal_required=False)))
    install_process_state(
        dev,  # type: ignore[arg-type]
        BaseServiceSettings(_env_file=None, env=EnvName.DEV),
        b"k" * 32,
    )
    assert isinstance(dev.state.sessions, MemorySessionStore)
    assert not hasattr(dev.state.chat, "event_bus")


class _MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expiry: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value
        if ex is not None:
            self.expiry[key] = ex

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def ttl(self, key: str) -> int:
        if key not in self.values:
            return -2
        return self.expiry.get(key, -1)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


@pytest.mark.unit
async def test_two_replicas_share_a_valkey_session() -> None:
    client = _MemoryRedis()
    first = ValkeySessionStore(b"k" * 32, "redis://unused", client=client)
    second = ValkeySessionStore(b"k" * 32, "redis://unused", client=client)
    session_id, data = new_session(uuid.uuid4(), uuid.uuid4())
    await first.put(session_id, data, 60)
    loaded = await second.get(session_id)
    assert loaded is not None
    assert loaded.csrf_token == data.csrf_token
    await second.delete(session_id)
    assert await first.get(session_id) is None


class _MemoryStream:
    def __init__(self) -> None:
        self.rows: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self._n = 0

    async def xadd(
        self,
        key: str,
        fields: dict[str, str],
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        del approximate
        self._n += 1
        message_id = f"{self._n}-0"
        bucket = self.rows.setdefault(key, [])
        bucket.append((message_id, dict(fields)))
        if maxlen is not None and len(bucket) > maxlen:
            del bucket[: len(bucket) - maxlen]
        return message_id

    async def xread(
        self,
        streams: dict[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        del block
        found: list[tuple[str, list[tuple[str, dict[str, str]]]]] = []
        for key, last in streams.items():
            newer = [item for item in self.rows.get(key, []) if _stream_after(item[0], last)]
            if count is not None:
                newer = newer[:count]
            if newer:
                found.append((key, newer))
        return found


def _stream_after(message_id: str, last: str) -> bool:
    def parts(value: str) -> tuple[int, int]:
        left, _, right = value.partition("-")
        return int(left), int(right or "0")

    return parts(message_id) > parts(last)


@pytest.mark.unit
async def test_run_events_reach_a_second_replica() -> None:
    shared = _MemoryStream()
    writer = ValkeyRunBus("redis://unused", client=shared)
    reader = ValkeyRunBus("redis://unused", client=shared)
    run_id = uuid.uuid4()
    await writer.add(run_id, '{"seq": 1, "type": "run.started", "data": {}}')
    _cursor, events = await reader.take(run_id, "0-0")
    assert events[0]["type"] == "run.started"
    assert events[0]["seq"] == 1


@pytest.mark.unit
def test_idempotency_body_round_trip() -> None:
    stored = StoredResponse(request_hash="abc", status_code=200, body=b'{"ok":true}')
    assert decode_body(encode_body(stored.body)) == stored.body
    assert decode_body(None) is None
    assert encode_body(None) is None


@pytest.mark.unit
async def test_rate_limiter_retries_then_denies_without_latching() -> None:
    class _Flaky:
        def __init__(self) -> None:
            self.calls = 0

        async def incr(self, key: str) -> int:
            del key
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("blip")
            return 1

        async def expire(self, key: str, seconds: int) -> None:
            del key, seconds

    flaky = _Flaky()
    bucket = ValkeyTokenBucket("redis://unused", client=flaky, pause_s=0)
    allowed = await bucket.take("tenant", 5)
    assert allowed.allowed
    assert flaky.calls == 2

    class _Down:
        async def incr(self, key: str) -> int:
            del key
            raise ConnectionError("down")

        async def expire(self, key: str, seconds: int) -> None:
            del key, seconds

    closed = ValkeyTokenBucket("redis://unused", client=_Down(), attempts=3, pause_s=0)
    first = await closed.take("tenant", 5)
    second = await closed.take("tenant", 5)
    assert not first.allowed and not second.allowed


def _queued(service: ChatService) -> uuid.UUID:
    run_id = uuid.uuid4()
    service.runs[run_id] = {
        "id": run_id,
        "tenant_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "status": "queued",
        "temporal_workflow_id": f"run-{run_id}",
    }
    service.events[run_id] = []
    return run_id


@pytest.mark.unit
async def test_required_temporal_does_not_generate_in_process() -> None:
    service = ChatService(fake_models_allowed=False)
    service.temporal_required = True
    run_id = _queued(service)
    await service._start_turn(run_id, "hello", [])
    error = service.runs[run_id]["error"]
    assert isinstance(error, dict)
    assert service.runs[run_id]["status"] == "failed"
    assert error["code"] == "interrupted"
    assert error["reason"] == "not_resumed"


class _MissingWorkflow:
    def get_workflow_handle(self, workflow_id: str) -> _MissingWorkflow:
        del workflow_id
        return self

    async def describe(self) -> None:
        raise RPCError("missing", RPCStatusCode.NOT_FOUND, b"")


@pytest.mark.unit
def test_publish_without_a_loop_is_a_no_op() -> None:
    bus = ValkeyRunBus("redis://unused", client=_MemoryStream())
    bus.publish(uuid.uuid4(), {"seq": 1, "type": "run.started"})
    assert bus._pending == set()


@pytest.mark.unit
async def test_publish_and_listen_share_the_stream() -> None:
    shared = _MemoryStream()
    bus = ValkeyRunBus("redis://unused", client=shared)
    run_id = uuid.uuid4()
    bus.publish(run_id, {"seq": 4, "type": "run.completed", "data": {}})
    pending = tuple(bus._pending)
    assert pending
    await pending[0]
    stream = bus.listen(run_id)
    event = await anext(stream)
    await stream.aclose()
    assert event["type"] == "run.completed"


@pytest.mark.unit
async def test_a_bad_stream_payload_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _MemoryStream()
    bus = ValkeyRunBus("redis://example")
    monkeypatch.setattr("ar_common.valkey.valkey_client", lambda *_args, **_kwargs: client)
    run_id = uuid.uuid4()
    await client.xadd(f"ar:run:{run_id}", {"payload": "not-json"})
    await client.xadd(f"ar:run:{run_id}", {"payload": "[]"})
    _cursor, events = await bus.take(run_id, "0-0")
    assert events == []


@pytest.mark.unit
def test_idempotency_body_rejects_a_foreign_shape() -> None:
    assert decode_body("nope") is None
    assert decode_body({"b64": ""}) is None
    assert decode_body({"b64": "abc"}) is None


@pytest.mark.unit
async def test_idempotency_store_reads_and_writes_through_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant = str(uuid.uuid4())
    row = SimpleNamespace(
        request_hash="hash-1",
        status_code=201,
        response_body=encode_body(b'{"ok":true}'),
    )

    class _Session:
        def __init__(self) -> None:
            self.statement: object = None

        async def get(self, _model: object, _key: object) -> object:
            return row

        async def execute(self, statement: object) -> None:
            self.statement = statement

    session = _Session()

    class _Context:
        async def __aenter__(self) -> _Session:
            return session

        async def __aexit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(
        "ar_domain.events.idempotency_pg.tenant_session", lambda *_a, **_k: _Context()
    )
    monkeypatch.setattr("ar_domain.events.idempotency_pg.get_engine", lambda _url: object())
    store = PostgresIdempotencyStore("postgresql+asyncpg://unused")
    assert await store.get(("not-a-uuid", "person", "key")) is None
    loaded = await store.get((tenant, "person", "key"))
    assert loaded is not None and loaded.status_code == 201 and loaded.body == b'{"ok":true}'
    await store.put(("not-a-uuid", "person", "key"), StoredResponse("h", 200, b"x"))
    await store.put((tenant, "person", "key"), StoredResponse("hash-1", 201, b'{"ok":true}'))
    assert session.statement is not None

    def explode(*_args: object, **_kwargs: object) -> object:
        raise ConnectionError("down")

    monkeypatch.setattr("ar_domain.events.idempotency_pg.tenant_session", explode)
    with pytest.raises(UnavailableError):
        await store.get((tenant, "person", "key"))
    with pytest.raises(UnavailableError):
        await store.put((tenant, "person", "key"), StoredResponse("h", 500, None))


class _RaisingRedis(_MemoryRedis):
    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        del key, value, ex
        raise ConnectionError("down")

    async def get(self, key: str) -> str | None:
        del key
        raise ConnectionError("down")

    async def ttl(self, key: str) -> int:
        del key
        raise ConnectionError("down")

    async def delete(self, key: str) -> None:
        del key
        raise ConnectionError("down")


@pytest.mark.unit
async def test_valkey_session_errors_are_unavailable() -> None:
    store = ValkeySessionStore(b"k" * 32, "redis://unused", client=_RaisingRedis())
    session_id, data = new_session(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(UnavailableError):
        await store.put(session_id, data, 30)
    with pytest.raises(UnavailableError):
        await store.get(session_id)
    with pytest.raises(UnavailableError):
        await store.update(session_id, data)
    with pytest.raises(UnavailableError):
        await store.delete(session_id)


@pytest.mark.unit
async def test_session_update_keeps_a_missing_key() -> None:
    client = _MemoryRedis()
    store = ValkeySessionStore(b"k" * 32, "redis://unused", client=client)
    _session_id, data = new_session(uuid.uuid4(), uuid.uuid4())
    await store.update("missing", data)
    assert client.values == {}


@pytest.mark.unit
async def test_rate_limiter_reconnects_after_a_blip(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Fail:
        async def incr(self, key: str) -> int:
            del key
            raise ConnectionError("blip")

        async def expire(self, key: str, seconds: int) -> None:
            del key, seconds

    class _Ok:
        async def incr(self, key: str) -> int:
            del key
            return 2

        async def expire(self, key: str, seconds: int) -> None:
            del key, seconds

    clients = [_Fail(), _Ok()]

    def factory(*_args: object, **_kwargs: object) -> object:
        return clients.pop(0)

    monkeypatch.setattr("ar_common.valkey.valkey_client", factory)
    bucket = ValkeyTokenBucket("redis://shared", pause_s=0)
    decision = await bucket.take("k", 5)
    assert decision.allowed
    assert decision.remaining == 3


@pytest.mark.unit
async def test_a_corrupt_session_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _MemoryRedis()
    monkeypatch.setattr("ar_common.valkey.valkey_client", lambda *_a, **_k: client)
    store = ValkeySessionStore(b"k" * 32, "redis://shared")
    store._client()
    client.values["ar:sess:bad"] = "not-sealed"
    assert await store.get("bad") is None


@pytest.mark.unit
async def test_rate_limiter_builds_its_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _CountingRedis()
    monkeypatch.setattr("ar_common.valkey.valkey_client", lambda *_a, **_k: client)
    bucket = ValkeyTokenBucket("redis://shared")
    decision = await bucket.take("k", 5)
    assert decision.allowed
    assert client.counts == [1]


class _CountingRedis:
    def __init__(self) -> None:
        self.counts: list[int] = []

    async def incr(self, key: str) -> int:
        del key
        self.counts.append(1)
        return 1

    async def expire(self, key: str, seconds: int) -> None:
        del key, seconds


@pytest.mark.unit
async def test_readiness_checks_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    database_calls = {"n": 0}

    async def ping_database(url: str) -> None:
        database_calls["n"] += 1
        if not url:
            raise RuntimeError("empty")

    class _Valkey:
        def __init__(self, answer: object) -> None:
            self.answer = answer
            self.closed = False

        async def ping(self) -> object:
            return self.answer

        async def aclose(self) -> None:
            self.closed = True

    live = _Valkey(True)
    monkeypatch.setattr("ar_domain.db.engine.ping_database", ping_database)
    monkeypatch.setattr("ar_common.valkey.valkey_client", lambda *_a, **_k: live)
    await ping_postgres("postgresql+asyncpg://unused")
    await ping_valkey("redis://unused")
    assert live.closed
    assert database_calls["n"] == 1
    dead = _Valkey(False)
    monkeypatch.setattr("ar_common.valkey.valkey_client", lambda *_a, **_k: dead)
    with pytest.raises(RuntimeError):
        await ping_valkey("redis://unused")
    with pytest.raises(RuntimeError):
        await ping_temporal("  ", "default")

    class _Health:
        async def check_health(self, **_kwargs: object) -> bool:
            return False

    class _Connected:
        service_client = _Health()

    async def connect(*_args: object, **_kwargs: object) -> _Connected:
        return _Connected()

    monkeypatch.setattr("temporalio.client.Client.connect", connect)
    with pytest.raises(RuntimeError):
        await ping_temporal("temporal:7233", "")

    settings = _prod_settings(temporal_required=True)
    checks = api_readiness(settings)
    await checks["postgres"]()
    await checks["postgres"]()
    assert database_calls["n"] == 2
    monkeypatch.setattr(
        "ar_domain.db.engine.ping_database",
        _fail_database,
    )
    failing = api_readiness(_prod_settings())
    with pytest.raises(RuntimeError):
        await failing["postgres"]()
    with pytest.raises(RuntimeError):
        await failing["postgres"]()


async def _fail_database(_url: str) -> None:
    raise RuntimeError("down")


@pytest.mark.unit
async def test_database_ping_uses_the_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.db.engine import ping_database

    class _Connection:
        async def execute(self, _statement: object) -> None:
            return None

        async def __aenter__(self) -> _Connection:
            return self

        async def __aexit__(self, *_args: object) -> bool:
            return False

    class _Engine:
        def connect(self) -> _Connection:
            return _Connection()

    monkeypatch.setattr("ar_domain.db.engine.get_engine", lambda _url: _Engine())
    await ping_database("postgresql+asyncpg://unused")


class _Workflow:
    def __init__(self, *, start: object = None, described: object = None) -> None:
        self.started = False
        self._start = start
        self._described = described

    async def start_workflow(self, *_args: object, **_kwargs: object) -> None:
        self.started = True
        if isinstance(self._start, Exception):
            raise self._start

    def get_workflow_handle(self, _workflow_id: str) -> _Workflow:
        return self

    async def describe(self) -> object:
        if isinstance(self._described, Exception):
            raise self._described
        return self._described


@pytest.mark.unit
async def test_temporal_start_paths_do_not_run_in_process() -> None:
    service = ChatService(fake_models_allowed=False)
    service.watch_polls = 0
    service.temporal_required = True
    started = _Workflow()
    service.temporal_client = started
    run_id = _queued(service)
    await service._start_turn(run_id, "hello", [])
    assert started.started
    assert service.runs[run_id]["status"] == "queued"

    duplicate = type("WorkflowAlreadyStartedError", (Exception,), {})("dup")
    service.temporal_client = _Workflow(start=duplicate)
    again = _queued(service)
    await service._start_turn(again, "hello", [])
    assert service.runs[again]["status"] == "queued"

    service.temporal_client = _Workflow(start=ConnectionError("down"))
    lost = _queued(service)
    await service._start_turn(lost, "hello", [])
    error = service.runs[lost]["error"]
    assert isinstance(error, dict) and error["reason"] == "not_resumed"

    service.temporal_client = object()
    missing = _queued(service)
    await service._start_turn(missing, "hello", [])
    assert service.runs[missing]["error"]["reason"] == "not_resumed"  # type: ignore[index]

    service.temporal_required = False

    async def generated(run: uuid.UUID, _text: str, _names: list[str]) -> None:
        service.runs[run]["status"] = "generated"

    service.generate = generated  # type: ignore[method-assign]
    service.temporal_client = None
    local = _queued(service)
    await service._start_turn(local, "hello", [])
    assert service.runs[local]["status"] == "generated"


@pytest.mark.unit
async def test_a_finished_workflow_and_the_event_bus() -> None:
    service = ChatService(fake_models_allowed=False)
    run_id = _queued(service)
    assert await service._workflow_gone(run_id) is False
    service.runs[run_id]["status"] = "completed"
    service.temporal_client = object()
    assert await service._workflow_gone(run_id) is False
    service.runs[run_id]["status"] = "running"
    assert await service._workflow_gone(run_id) is False

    class _NoDescribe:
        def get_workflow_handle(self, _workflow_id: str) -> object:
            return object()

    service.temporal_client = _NoDescribe()
    assert await service._workflow_gone(run_id) is False
    quiet = _Workflow()
    service.temporal_client = quiet
    assert await service._workflow_gone(run_id) is False
    done = _Workflow(described=SimpleNamespace(status=SimpleNamespace(name="COMPLETED")))
    service.temporal_client = done
    assert await service._workflow_gone(run_id) is True
    running = _Workflow(described=SimpleNamespace(status=SimpleNamespace(name="RUNNING")))
    service.temporal_client = running
    assert await service._workflow_gone(run_id) is False
    service.temporal_client = _Workflow(described=RuntimeError("blip"))
    assert await service._workflow_gone(run_id) is False

    service.event_bus = object()
    service._publish_event(run_id, {"seq": 1})

    class _Broken:
        def publish(self, _run_id: uuid.UUID, _event: dict[str, object]) -> None:
            raise RuntimeError("bus down")

    service.event_bus = _Broken()
    service._publish_event(run_id, {"seq": 1})

    class _Stream:
        async def listen(self, _run_id: uuid.UUID) -> AsyncIterator[object]:
            yield {"seq": 1, "type": "run.started"}
            yield "skip"
            raise RuntimeError("closed")

    service.event_bus = _Stream()
    queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
    await service._pump_bus(run_id, queue)
    assert queue.get_nowait()["type"] == "run.started"
    service.event_bus = object()
    await service._pump_bus(run_id, queue)


@pytest.mark.unit
async def test_a_lost_workflow_is_marked_not_resumed() -> None:
    service = ChatService(fake_models_allowed=False)
    service.temporal_client = _MissingWorkflow()
    service.watch_polls = 1
    run_id = _queued(service)
    service.runs[run_id]["status"] = "running"
    await service._watch(run_id)
    error = service.runs[run_id]["error"]
    assert isinstance(error, dict)
    assert error["code"] == "interrupted"
    assert error["reason"] == "not_resumed"

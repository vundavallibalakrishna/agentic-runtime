"""Stage 1 safe process. Proof label: unit (in-process, no network, no model)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError
from temporalio.service import RPCError, RPCStatusCode

from ar_api.auth.session import MemorySessionStore, ValkeySessionStore, new_session
from ar_api.idempotency_store import PostgresIdempotencyStore, decode_body, encode_body
from ar_api.process import install_process_state
from ar_api.ratelimit import ValkeyTokenBucket
from ar_api.readiness import readiness_names
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
async def test_a_lost_workflow_is_marked_not_resumed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(seconds: float) -> None:
        del seconds

    monkeypatch.setattr("ar_domain.chat.service.asyncio.sleep", no_sleep)
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

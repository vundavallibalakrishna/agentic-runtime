"""Stage 9 shared request-path state. Proof label: unit (no network, no model)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import orjson
import pytest
from pydantic import SecretStr

from ar_common.settings import BaseServiceSettings, EnvName, get_settings, set_settings
from ar_domain.chat.service import ChatService
from ar_domain.process_state import (
    ProcessLocalStateRefusedError,
    ValkeyJsonBook,
    install_shared_state,
    require_shared_request_state,
    take_window,
)
from ar_domain.readmodel.boot import build_product_store
from ar_domain.readmodel.model import RepositoryReadModel
from ar_domain.sandboxes.manager_launch import register_worker_sandbox

pytestmark = pytest.mark.unit

_SECRET = SecretStr("unit-test-cursor-secret")


class _Valkey:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.counts: dict[str, int] = {}
        self.members: set[str] = set()

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def sadd(self, key: str, member: str) -> int:
        del key
        self.members.add(member)
        return 1

    def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, ttl: int) -> bool:
        del key, ttl
        return True


def _staging() -> BaseServiceSettings:
    return BaseServiceSettings(_env_file=None, env=EnvName.STAGING, cursor_secret=_SECRET)


def test_staging_refuses_a_process_local_book(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_SANDBOX_MANAGER_URL", raising=False)
    monkeypatch.setattr("redis.Redis.from_url", lambda *_a, **_k: _Valkey())
    previous = get_settings()
    settings = _staging()
    set_settings(settings)
    try:
        store = build_product_store(settings, allow_loopback=False, fake_models_allowed=False)
        # Building the store attaches the Valkey books, so no entry point can forget them.
        require_shared_request_state(store, settings)
        store.builder_sessions = {}
        with pytest.raises(ProcessLocalStateRefusedError):
            require_shared_request_state(store, settings)
        with pytest.raises(ProcessLocalStateRefusedError):
            register_worker_sandbox(store, settings)
    finally:
        set_settings(previous)
    assert isinstance(store, RepositoryReadModel)


def test_two_stores_share_a_valkey_session_and_window(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Valkey()
    monkeypatch.setattr("redis.Redis.from_url", lambda *_a, **_k: client)
    previous = get_settings()
    settings = _staging()
    set_settings(settings)
    try:
        first = build_product_store(settings, allow_loopback=False, fake_models_allowed=False)
        second = build_product_store(settings, allow_loopback=False, fake_models_allowed=False)
        install_shared_state(first, settings)
        install_shared_state(second, settings)
    finally:
        set_settings(previous)
    session_id = uuid.uuid4()
    tenant = uuid.uuid4()
    first.builder_sessions[session_id] = {
        "id": session_id,
        "tenant_id": tenant,
        "user_id": uuid.uuid4(),
        "instruction": "draft a helper",
        "messages": [{"role": "user", "text": "draft a helper"}],
    }
    loaded = second.builder_sessions.get(session_id)
    assert isinstance(loaded, dict)
    assert loaded["tenant_id"] == tenant
    assert loaded["instruction"] == "draft a helper"
    assert isinstance(first.builder_sessions, ValkeyJsonBook)
    allowed, remaining = take_window(first, "agent-api:one", 2)  # type: ignore[misc]
    assert allowed is True
    assert remaining == 1
    again, left = take_window(second, "agent-api:one", 2)  # type: ignore[misc]
    assert again is True and left == 0
    blocked, none_left = take_window(second, "agent-api:one", 2)  # type: ignore[misc]
    assert blocked is False and none_left == 0


def test_dev_keeps_a_process_local_window() -> None:
    store = ChatService()
    assert take_window(store, "tool:local", 5) is None


def test_a_down_valkey_refuses_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Down:
        def ping(self) -> bool:
            raise ConnectionError("down")

    monkeypatch.setattr("ar_common.valkey.valkey_sync_client", lambda *_a, **_k: _Down())
    previous = get_settings()
    settings = _staging()
    set_settings(settings)
    try:
        with pytest.raises(ProcessLocalStateRefusedError):
            build_product_store(settings, allow_loopback=False, fake_models_allowed=False)
    finally:
        set_settings(previous)


def test_a_rate_client_error_denies_the_hit() -> None:
    class _Down:
        def incr(self, key: str) -> int:
            del key
            raise RuntimeError("down")

    store = ChatService()
    store.valkey_client = _Down()
    allowed, remaining = take_window(store, "tool:x", 5)  # type: ignore[misc]
    assert allowed is False
    assert remaining == 0


def test_builder_book_miss_and_persist() -> None:
    client = _Valkey()
    book = ValkeyJsonBook(client)
    assert book.get(uuid.uuid4()) is None
    book.persist(uuid.uuid4())
    assert client.values == {}


def test_worker_registers_the_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.sandboxes.manager_launch import SandboxManagerLauncher

    monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", "http://sandbox-manager:8003")
    monkeypatch.setenv("AR_SANDBOX_DRIVER", "kubernetes")
    store = ChatService()
    register_worker_sandbox(store, BaseServiceSettings(_env_file=None, env=EnvName.DEV))
    assert isinstance(store.sandbox_launcher, SandboxManagerLauncher)


class _Result:
    def __init__(self, row: object) -> None:
        self._row = row

    def first(self) -> object:
        return self._row


class _Session:
    def __init__(self, present: bool = True, fail: bool = False, missing_table: str = "") -> None:
        self.present = present
        self.fail = fail
        self.missing_table = missing_table
        self.wrote = 0

    def begin_nested(self) -> _Session:
        return self

    async def __aenter__(self) -> _Session:
        if self.fail:
            from sqlalchemy.exc import IntegrityError

            raise IntegrityError("insert", {}, Exception("check"))
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, statement: object, params: object = None) -> _Result:
        if isinstance(params, dict) and (
            "argument_constraints" in params or "slug" in params or "content_hash" in params
        ):
            self.wrote += 1
        sql = str(statement)
        if self.missing_table and f"FROM {self.missing_table}" in sql:
            return _Result(None)
        return _Result((1,) if self.present else None)


async def test_shared_rows_skip_a_missing_tool_and_write_a_queue() -> None:
    from datetime import UTC, datetime, timedelta

    from ar_domain.durable.stage9 import save_review_queues, save_standing_approvals

    missing = _Session(present=False)
    standing_id = uuid.uuid4()
    await save_standing_approvals(
        missing,  # type: ignore[arg-type]
        [
            {
                "id": standing_id,
                "tenant_id": uuid.uuid4(),
                "granted_by_user_id": uuid.uuid4(),
                "agent_id": uuid.uuid4(),
                "tool_id": uuid.uuid4(),
                "expires_at": datetime.now(UTC) + timedelta(days=1),
                "uses": 0,
            }
        ],
    )
    assert missing.wrote == 0
    present = _Session()
    await save_standing_approvals(
        present,  # type: ignore[arg-type]
        [
            {
                "id": standing_id,
                "tenant_id": uuid.uuid4(),
                "granted_by_user_id": uuid.uuid4(),
                "agent_id": uuid.uuid4(),
                "tool_id": uuid.uuid4(),
                "argument_constraints": [],
                "expires_at": datetime.now(UTC) + timedelta(days=1),
                "uses": 1,
            }
        ],
    )
    assert present.wrote == 1
    from ar_domain.durable.stage9 import save_review_items

    items = _Session()
    await save_review_items(
        items,  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "queue_id": uuid.uuid4(),
                "subject_type": "file",
                "subject_id": uuid.uuid4(),
                "content_hash": "abc",
                "statement_text": "reviewed",
                "statement_hash": "def",
                "status": "pending",
                "preparer_principal_type": "user",
                "preparer_principal_id": uuid.uuid4(),
            }
        ],
    )
    assert items.wrote == 1
    queues = _Session()
    await save_review_queues(
        queues,  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "slug": "files",
                "name": "Files",
                "subject_type": "file",
                "levels": [{"level": 1}],
                "statement_template": "reviewed",
            }
        ],
    )
    assert queues.wrote == 1


def test_shared_books_cover_the_remaining_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.process_state import _plain, bind_unit, remember_builder_session

    client = _Valkey()
    bind_unit(ChatService(), ChatService())
    holder = ChatService()
    holder.valkey_client = client
    unit = ChatService()
    bind_unit(holder, unit)
    assert isinstance(unit.builder_sessions, ValkeyJsonBook)
    require_shared_request_state(holder, BaseServiceSettings(_env_file=None, env=EnvName.DEV))
    holder.builder_sessions = {}
    previous = get_settings()
    local = ChatService()
    set_settings(_staging())
    try:
        with pytest.raises(ProcessLocalStateRefusedError):
            require_shared_request_state(holder, _staging())
        with pytest.raises(ProcessLocalStateRefusedError):
            take_window(local, "tool:x", 1)
    finally:
        set_settings(previous)
    remember_builder_session(ChatService(), uuid.uuid4())
    session_id = uuid.uuid4()
    unit.builder_sessions[session_id] = {"id": session_id, "created_at": datetime.now(UTC)}
    loaded = unit.builder_sessions.get(session_id)
    assert isinstance(loaded, dict)
    book = unit.builder_sessions
    book.client.values[book._redis_key("list")] = "[1]"
    assert book._read("list") is None
    book.client.values[book._redis_key("bad")] = orjson.dumps(
        {"id": "not-a-uuid", "created_at": "nope"}
    ).decode()
    assert isinstance(book._read("bad"), dict)
    with pytest.raises(TypeError):
        _plain(object())
    monkeypatch.setenv("AR_SANDBOX_IMAGE", "ar-sandbox:dev")
    monkeypatch.delenv("AR_SANDBOX_MANAGER_URL", raising=False)
    monkeypatch.delenv("AR_SANDBOX_DRIVER", raising=False)

    class _Launcher:
        def __init__(self, image: str, network: str | None = None) -> None:
            self.image = image
            self.network = network

    monkeypatch.setattr("ar_common.sandbox_docker.DockerSandboxLauncher", _Launcher)
    store = ChatService()
    register_worker_sandbox(
        store,
        BaseServiceSettings(_env_file=None, env=EnvName.DEV, sandbox_allow_unisolated=True),
    )
    assert store.sandbox_launcher.image == "ar-sandbox:dev"  # type: ignore[attr-defined]


async def test_shared_rows_skip_incomplete_and_a_failed_insert() -> None:
    from ar_domain.durable.stage9 import (
        save_review_items,
        save_review_queues,
        save_standing_approvals,
    )

    session = _Session()
    await save_standing_approvals(session, [{"id": "nope"}])  # type: ignore[arg-type]
    expires = datetime.now(UTC) + timedelta(days=1)
    await save_standing_approvals(
        session,  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "granted_by_user_id": uuid.uuid4(),
                "tool_id": uuid.uuid4(),
                "expires_at": expires,
            }
        ],
    )
    await save_standing_approvals(
        _Session(missing_table="users"),  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "granted_by_user_id": uuid.uuid4(),
                "agent_id": uuid.uuid4(),
                "tool_id": uuid.uuid4(),
                "expires_at": expires,
            }
        ],
    )
    await save_standing_approvals(
        _Session(missing_table="agents"),  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "granted_by_user_id": uuid.uuid4(),
                "agent_id": uuid.uuid4(),
                "tool_id": uuid.uuid4(),
                "expires_at": expires,
            }
        ],
    )
    await save_review_queues(session, [{"id": uuid.uuid4()}])  # type: ignore[arg-type]
    await save_review_items(session, [{"id": uuid.uuid4()}])  # type: ignore[arg-type]
    await save_review_items(
        session,  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "queue_id": uuid.uuid4(),
                "subject_id": uuid.uuid4(),
                "preparer_principal_id": uuid.uuid4(),
                "status": "nope",
                "preparer_principal_type": "user",
            }
        ],
    )
    await save_review_queues(
        _Session(fail=True),  # type: ignore[arg-type]
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": uuid.uuid4(),
                "slug": "files",
                "subject_type": "file",
            }
        ],
    )

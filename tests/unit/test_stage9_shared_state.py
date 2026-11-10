"""Stage 9 shared request-path state. Proof label: unit (no network, no model)."""

from __future__ import annotations

import uuid

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
    previous = get_settings()
    settings = _staging()
    set_settings(settings)
    try:
        store = build_product_store(settings, allow_loopback=False, fake_models_allowed=False)
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

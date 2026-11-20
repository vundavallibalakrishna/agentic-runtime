"""Which usage a quota counts, who it binds, and what the counters do when Valkey is lost."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from ar_domain.tools.named_secrets import (
    install_named_secret,
    read_named_secret,
    stage_named_secret,
    write_named_secret,
)
from ar_domain.usage.logic import UsageRecord
from ar_domain.usage.quotas import (
    MemoryCounters,
    ValkeyCounters,
    applies,
    contribution,
    counter_key,
    in_scope,
    subject_for,
    warn_key,
)

_NOW = datetime.now(UTC)


def _record(**more: object) -> UsageRecord:
    values: dict[str, object] = {
        "tenant_id": "t1",
        "occurred_at": _NOW,
        "metric": "model_input_tokens",
        "quantity": 120,
        "cost_micros": 7,
        "dedupe_key": "k",
        **more,
    }
    return UsageRecord(**values)  # type: ignore[arg-type]


def _quota(scope: str, scope_id: object = None, **more: object) -> dict[str, object]:
    return {"tenant_id": "t1", "scope_type": scope, "scope_id": scope_id, **more}


def test_a_quota_counts_only_the_usage_in_its_scope() -> None:
    assert in_scope(_quota("tenant"), _record()) is True
    assert in_scope(_quota("tenant"), _record(tenant_id="t2")) is False
    assert in_scope(_quota("team", "team-1"), _record(team_id="team-1")) is True
    assert in_scope(_quota("team", "team-1"), _record()) is False
    assert in_scope(_quota("agent", "a1"), _record(agent_id="a1")) is True
    assert in_scope(_quota("agent", "a1"), _record(agent_id="a2")) is False
    assert in_scope(_quota("user"), _record(user_id="u1")) is True
    assert in_scope(_quota("user"), _record()) is False
    assert in_scope(_quota("user", "u1"), _record(user_id="u2")) is False
    assert in_scope(_quota("api_key", "key-1"), _record(api_key_id="key-1")) is True
    assert in_scope(_quota("api_key", "key-1"), _record()) is False
    assert in_scope(_quota("something-else"), _record()) is False


def test_a_quota_binds_the_caller_it_names() -> None:
    def bound(quota: dict[str, object], **who: object) -> bool:
        caller: dict[str, object] = {
            "tenant_id": "t1",
            "user_id": "u1",
            "team_ids": {"team-1"},
            "agent_id": "a1",
            **who,
        }
        return applies(quota, **caller)  # type: ignore[arg-type]

    assert bound(_quota("tenant")) is True
    assert bound(_quota("tenant"), tenant_id="t2") is False
    assert bound(_quota("team", "team-1")) is True
    assert bound(_quota("team", "team-2")) is False
    assert bound(_quota("team")) is False
    assert bound(_quota("agent", "a1")) is True
    assert bound(_quota("agent", "a1"), agent_id=None) is False
    assert bound(_quota("user")) is True
    assert bound(_quota("user", "u2")) is False
    assert bound(_quota("user"), user_id=None) is False
    assert bound(_quota("api_key", "key-1"), api_key_id="key-1") is True
    assert bound(_quota("api_key", "key-1")) is False
    assert bound(_quota("something-else")) is False


def test_what_a_usage_row_adds_to_each_kind_of_quota() -> None:
    assert contribution("model_tokens", _record()) == 120
    assert contribution("cost_micros", _record()) == 7
    assert contribution("tool_calls", _record(metric="tool_calls", quantity=3)) == 3
    assert contribution("tool_calls", _record()) == 0
    assert subject_for(_quota("user"), "u1") == "u1"
    assert subject_for(_quota("user"), None) == ""
    assert subject_for(_quota("user", "u1"), "u1") == ""
    assert subject_for(_quota("tenant"), "u1") == ""
    assert counter_key("q", "2026-11") == "ar:q:q:2026-11"
    assert counter_key("q", "2026-11", "u1") == "ar:q:q:u1:2026-11"
    assert warn_key("q", "2026-11") == "ar:qwarn:q:2026-11"
    assert warn_key("q", "2026-11", "u1") == "ar:qwarn:q:u1:2026-11"


class _Valkey:
    """A client that answers until ``down`` is set, then refuses every call."""

    def __init__(self) -> None:
        self.rows: dict[str, int] = {}
        self.down = False

    def _check(self) -> None:
        if self.down:
            raise ConnectionError("connection lost")

    def incrby(self, key: str, amount: int) -> int:
        self._check()
        self.rows[key] = self.rows.get(key, 0) + amount
        return self.rows[key]

    def expire(self, key: str, seconds: int) -> None:
        del key, seconds
        self._check()

    def get(self, key: str) -> int | None:
        self._check()
        return self.rows.get(key)

    def set(self, key: str, value: int, *, nx: bool = False, ex: int = 0) -> bool:
        del ex
        self._check()
        if nx and key in self.rows:
            return False
        self.rows[key] = value
        return True


def test_counters_count_in_valkey_and_keep_counting_when_it_is_lost() -> None:
    later = _NOW + timedelta(hours=1)
    client = _Valkey()
    counters = ValkeyCounters(client, MemoryCounters({}, threading.Lock()))
    assert counters.add("a", 5, later) == 5
    assert counters.add("a", 2, later) == 7
    assert counters.read("a") == 7
    assert counters.read("never") == 0
    counters.put("b", 40, later)
    assert counters.read("b") == 40
    assert counters.claim("warned", later) is True
    assert counters.claim("warned", later) is False

    # Valkey goes away. Nothing is refused: the process counts on its own from here.
    client.down = True
    assert counters.read("a") == 0
    assert counters.open is True
    assert counters.add("a", 3, later) == 3
    assert counters.read("a") == 3
    counters.put("b", 9, later)
    assert counters.read("b") == 9
    assert counters.claim("again", later) is True
    assert counters.claim("again", later) is False

    for call in ("add", "put", "claim"):
        lost = _Valkey()
        lost.down = True
        fresh = ValkeyCounters(lost, MemoryCounters({}, threading.Lock()))
        if call == "add":
            assert fresh.add("x", 1, later) == 1
        elif call == "put":
            fresh.put("x", 4, later)
            assert fresh.read("x") == 4
        else:
            assert fresh.claim("x", later) is True
        assert fresh.open is True


def test_a_secret_the_product_keeps_is_staged_installed_and_replaced() -> None:
    from types import SimpleNamespace

    store = SimpleNamespace()
    tenant = uuid.uuid4()
    assert read_named_secret(store, tenant, "token") is None
    first = stage_named_secret(tenant, "token", "one")
    install_named_secret(store, first)
    assert read_named_secret(store, tenant, "token") == "one"
    # A second committed row with the same name takes the first one's place.
    second = stage_named_secret(tenant, "token", "two")
    install_named_secret(store, second)
    assert list(store.named_secrets) == [second["id"]]
    assert read_named_secret(store, tenant, "token") == "two"
    write_named_secret(store, tenant, "token", "three")
    assert read_named_secret(store, tenant, "token") == "three"
    store.named_secrets[(str(tenant), "plain")] = "kept as text"
    store.named_secrets[(str(tenant), "bytes")] = b"kept as bytes"
    assert read_named_secret(store, tenant, "plain") == "kept as text"
    assert read_named_secret(store, tenant, "bytes") == "kept as bytes"
    store.named_secrets["junk"] = "not a row"
    second["ciphertext"] = memoryview(b"damaged")
    assert read_named_secret(store, tenant, "token") is None

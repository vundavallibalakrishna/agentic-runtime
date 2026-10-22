"""Quotas, plan limits and usage reports. Spec 17 §2 and spec 02 §6."""

import threading
import time
import uuid
from datetime import UTC, datetime

import pytest

from ar_common.errors import ForbiddenError, PlanLimitReachedError, QuotaExceededError
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.plan_limits import LimitContext, check, guard, limit_keys
from ar_domain.identity.seed import plan_limits
from ar_domain.usage.logic import UsageRecord
from ar_domain.usage.quotas import MemoryCounters, period_key, zone
from ar_domain.usage.reports import usage_csv
from ar_domain.usage.service import UsageBook, note

_CEILINGS = frozenset({"max_sandbox_cpu_millis", "max_sandbox_memory_mb"})


def _actor(tenant: uuid.UUID | None = None, user: uuid.UUID | None = None) -> Actor:
    return Actor(tenant or demo_id("tenant"), user or demo_id("admin"), PERMISSION_KEYS)


def test_period_keys_follow_the_tenant_zone() -> None:
    moment = datetime(2026, 10, 22, 20, 30, tzinfo=UTC)
    assert period_key(moment, "Asia/Kolkata", "day") == "2026-10-23"
    assert period_key(moment, "Asia/Kolkata", "month") == "2026-10"
    assert (
        period_key(datetime(2026, 1, 31, 18, 30, tzinfo=UTC), "Asia/Kolkata", "month") == "2026-02"
    )
    assert zone("Not/AZone").key == "Asia/Kolkata"


def test_counters_converge_with_daily_and_warn_once() -> None:
    store = ChatService()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    actor = _actor(tenant, user)
    book = UsageBook(store)
    created = book.create(
        actor,
        {
            "scope_type": "user",
            "scope_id": user,
            "metric": "model_tokens",
            "period": "day",
            "limit_value": 100,
            "action": "warn",
            "warn_at_pct": 80,
        },
    )
    for index, quantity in enumerate((80, 10)):
        note(
            store,
            UsageRecord(
                str(tenant),
                utcnow(),
                "model_input_tokens",
                quantity,
                0,
                f"warn:{index}",
                user_id=str(user),
                source="model-gateway",
            ),
        )
    warnings = [row for row in store.notifications if row.get("kind") == "quota_warning"]
    topics = [row.get("topic") for row in store.domain_events]
    assert warnings
    assert topics.count("quota.warning") == 1
    book.materialise()
    daily = sum(item.quantity for item in store.usage_daily.values())
    assert daily == 90
    view = book.list_quotas(actor)
    row = next(item for item in view if item["id"] == created["id"])
    assert row["used"] == 90


def test_counter_increments_are_safe_across_threads() -> None:
    slots: dict[str, tuple[int, datetime]] = {}
    counters = MemoryCounters(slots, threading.Lock())
    expires = utcnow().replace(year=utcnow().year + 1)
    errors: list[BaseException] = []

    def spend() -> None:
        try:
            for _ in range(50):
                counters.add("ar:q:shared:2026-10-22", 1, expires)
        except BaseException as exc:  # noqa: BLE001 - surface the thread failure
            errors.append(exc)

    threads = [threading.Thread(target=spend) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert counters.read("ar:q:shared:2026-10-22") == 1000


def test_enforcement_stays_under_two_milliseconds() -> None:
    store = ChatService()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    book = UsageBook(store)
    book.create(
        _actor(tenant, user),
        {
            "scope_type": "tenant",
            "metric": "runs",
            "period": "day",
            "limit_value": 10_000,
            "action": "block",
        },
    )
    samples: list[float] = []
    for _ in range(200):
        started = time.perf_counter()
        book.assert_run(tenant, user, None)
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    assert samples[int(len(samples) * 0.95)] < 2


def test_ten_thousand_token_quota_blocks_with_a_clear_message() -> None:
    store = ChatService()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    book = UsageBook(store)
    book.create(
        _actor(tenant, user),
        {
            "scope_type": "user",
            "scope_id": user,
            "metric": "model_tokens",
            "period": "day",
            "limit_value": 10_000,
            "action": "block",
        },
    )
    note(
        store,
        UsageRecord(
            str(tenant),
            utcnow(),
            "model_input_tokens",
            10_000,
            0,
            "cap",
            user_id=str(user),
            source="model-gateway",
        ),
    )
    with pytest.raises(QuotaExceededError) as caught:
        book.assert_run(tenant, user, None)
    assert caught.value.detail.startswith("Quota reached.")
    assert "10,000" in caught.value.detail
    assert caught.value.metric == "model_tokens"


def test_csv_matches_the_daily_rows() -> None:
    store = ChatService()
    store.seed_showcase()
    actor = _actor()
    book = UsageBook(store)
    body = book.export_csv(actor, {})
    lines = [line for line in body.splitlines() if line]
    assert lines[0] == (
        "day,metric,user_email,team,agent_slug,model_alias,quantity,cost_micros,currency"
    )
    daily_qty = sum(item.quantity for item in store.usage_daily.values())
    exported = sum(int(line.split(",")[6]) for line in lines[1:])
    assert exported == daily_qty
    snapshot = usage_csv(
        [
            {
                "day": "2026-10-22",
                "metric": "model_input_tokens",
                "user_email": "admin@dev.local",
                "team": "",
                "agent_slug": "assistant",
                "model_alias": "reasoning",
                "quantity": 3,
                "cost_micros": 15,
            }
        ],
        "INR",
    )
    assert snapshot == (
        "day,metric,user_email,team,agent_slug,model_alias,quantity,cost_micros,currency\n"
        "2026-10-22,model_input_tokens,admin@dev.local,,assistant,reasoning,3,15,INR\n"
    )


def test_every_plan_limit_key_and_self_hosted_defaults() -> None:
    hosted = plan_limits("self_hosted")
    assert hosted["max_users"] is None
    assert hosted["max_agents"] == 200
    assert hosted["api_rpm"] == 6000
    keys = limit_keys()
    assert "monthly_cost_micros" not in keys
    assert "unit_prices" not in keys
    assert "features.widget" in keys
    for key in keys:
        if key.startswith("features."):
            name = key.removeprefix("features.")
            off = PlanLimits().model_dump(by_alias=False)
            off["features"][name] = False
            with pytest.raises(ForbiddenError) as caught:
                check(LimitContext(PlanLimits.model_validate(off), {}), key, 1)
            assert caught.value.detail == f"feature_not_in_plan:{name}"
            on = PlanLimits().model_dump(by_alias=False)
            on["features"][name] = True
            check(LimitContext(PlanLimits.model_validate(on), {}), key, 1)
            continue
        data = PlanLimits().model_dump(by_alias=False)
        if key.startswith("max_retention."):
            data["max_retention"][key.removeprefix("max_retention.")] = 0
            tight = PlanLimits.model_validate(data)
            with pytest.raises(PlanLimitReachedError) as caught:
                check(LimitContext(tight, {}), key, 1)
            assert caught.value.detail == key
            continue
        if key == "max_storage_gb":
            data["max_storage_gb"] = 1
            tight = PlanLimits.model_validate(data)
            with pytest.raises(PlanLimitReachedError) as caught:
                check(LimitContext(tight, {"max_storage_gb": 2 * 1024**3}), key, 1)
            assert caught.value.detail == key
            continue
        data[key] = 1 if key in _CEILINGS else 0
        tight = PlanLimits.model_validate(data)
        delta = 2 if key in _CEILINGS else 1
        with pytest.raises(PlanLimitReachedError) as caught:
            check(LimitContext(tight, {key: 0}), key, delta)
        assert caught.value.detail == key


def test_two_hundredth_agent_is_the_plan_cap() -> None:
    store = ChatService()
    store.seed_showcase()
    tenant = demo_id("tenant")
    settings = dict(store.tenant_settings.get(tenant) or {})
    settings["plan_limits"] = {"max_agents": 200}
    store.tenant_settings[tenant] = settings
    existing = sum(1 for row in store.agents.values() if row.get("tenant_id") == tenant)
    for index in range(200 - existing):
        store.agents[uuid.uuid4()] = {"tenant_id": tenant, "slug": f"pad-{index}"}
    with pytest.raises(PlanLimitReachedError) as caught:
        AgentLifecycle(store).create(_actor(), slug="one-more", name="One more")
    assert caught.value.detail == "max_agents"
    guard(store, tenant, "max_agents", 1, current=199)


def test_tool_sandbox_and_run_hooks_block() -> None:
    store = ChatService()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    book = UsageBook(store)
    actor = _actor(tenant, user)
    book.create(
        actor,
        {
            "scope_type": "tenant",
            "metric": "tool_calls",
            "period": "month",
            "limit_value": 0,
            "action": "block",
        },
    )
    with pytest.raises(QuotaExceededError):
        book.assert_tool(tenant, user, None)
    book.create(
        actor,
        {
            "scope_type": "tenant",
            "metric": "sandbox_cpu_seconds",
            "period": "day",
            "limit_value": 0,
            "action": "block",
        },
    )
    with pytest.raises(QuotaExceededError):
        book.assert_sandbox(tenant, user, None)
    book.create(
        actor,
        {
            "scope_type": "tenant",
            "metric": "runs",
            "period": "day",
            "limit_value": 0,
            "action": "block",
        },
    )
    with pytest.raises(QuotaExceededError):
        book.assert_run(tenant, user, None)

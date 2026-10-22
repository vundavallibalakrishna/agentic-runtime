"""Schedule preview, signatures, delivery and failure pause."""

import uuid
from datetime import UTC, datetime

from ar_common.ids import new_id
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.engine import (
    accept_routine_event,
    complete_routine_event,
    pause_for_owner,
    poll_routine_source,
    prepare_routine_run,
    reconcile_schedules,
    release_delivery,
)
from ar_domain.routines.schedule import preview_schedule
from ar_domain.routines.signature import header_for, idempotency_key, verify


def _actor() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=frozenset(
            {
                "routines:create",
                "routines:manage_all",
                "approvals:grant_standing",
                "agents:manage_all",
            }
        ),
        display_name="Admin",
    )


def _store() -> ChatService:
    service = ChatService()
    service.seed_demo()
    service.seed_showcase()
    return service


def _create(book: RoutineBook, **extra: object) -> dict[str, object]:
    store = book.store
    agent = store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    body: dict[str, object] = {
        "name": "Digest",
        "instructions": "Write the weekly digest.",
        "agent_id": agent["id"],
        "trigger": {"type": "schedule", "cron": "0 9 * * 1", "timezone": "Asia/Kolkata"},
        "delivery": [{"type": "slack", "channel": "#platform", "pre_approved": False}],
    }
    body.update(extra)
    return book.create(_actor(), body)


def test_preview_handles_ist_and_a_dst_zone() -> None:
    ist = preview_schedule("0 9 * * 1", "Asia/Kolkata")
    assert ist["valid"] is True
    assert ist["description"] == "Every Monday 09:00 IST"
    nxt = ist["next"]
    assert isinstance(nxt, list) and len(nxt) == 5
    york = preview_schedule("0 9 * * 1", "America/New_York")
    assert york["valid"] is True
    assert len(york["next"]) == 5  # type: ignore[arg-type]
    assert preview_schedule("not cron", "UTC")["valid"] is False
    assert preview_schedule("0 9 * * 1", "Mars/Base")["valid"] is False


def test_signature_is_timing_safe_and_expires() -> None:
    body = b'{"hello":"world"}'
    header = header_for("secret", body, 1_700_000_000)
    assert verify("secret", body, header, now=1_700_000_000)
    assert not verify("other", body, header, now=1_700_000_000)
    assert not verify("secret", body, header, now=1_700_000_000 + 301)
    assert idempotency_key(body, path_value="abc", header="ignored") == "abc"
    assert idempotency_key(body, path_value="", header="hdr") == "hdr"
    assert len(idempotency_key(body, path_value="", header="")) == 64


def test_delivery_waits_then_posts_once() -> None:
    store = _store()
    book = RoutineBook(store)
    created = _create(book)
    routine_id = uuid.UUID(str(created["id"]))
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="manual",
        idempotency_key="once",
        envelope={"type": "manual", "data": {}},
    )
    event_id = uuid.UUID(str(accepted["event_id"]))
    prepared = prepare_routine_run(store, routine_id, event_id)
    assert prepared["status"] == "ready"
    text = str(prepared["text"])
    assert 'trust="untrusted"' in text
    run = store.runs[uuid.UUID(str(prepared["run_id"]))]
    run["status"] = "completed"
    run["result_summary"] = "The week in brief."
    done = complete_routine_event(store, event_id)
    assert done["status"] == "waiting"
    deliveries = done["deliveries"]
    assert isinstance(deliveries, list)
    approval_id = uuid.UUID(str(deliveries[0]["approval_id"]))
    first = release_delivery(store, approval_id)
    second = release_delivery(store, approval_id)
    assert first["result"] == "posted"
    assert second.get("duplicate") is True
    assert len(store.delivery_posts) == 1


def test_standing_approval_posts_without_waiting() -> None:
    store = _store()
    book = RoutineBook(store)
    created = _create(
        book,
        delivery=[{"type": "slack", "channel": "#platform", "pre_approved": True}],
    )
    routine_id = uuid.UUID(str(created["id"]))
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="schedule",
        idempotency_key="standing",
        envelope={"type": "schedule"},
    )
    event_id = uuid.UUID(str(accepted["event_id"]))
    prepare_routine_run(store, routine_id, event_id)
    run_id = store.routine_events[event_id]["run_id"]
    store.runs[run_id]["status"] = "completed"
    done = complete_routine_event(store, event_id)
    assert done["status"] == "completed"
    assert store.delivery_posts[0]["target"] == "slack"


def test_duplicate_filter_cap_and_auto_pause() -> None:
    store = _store()
    book = RoutineBook(store)
    created = _create(book, event_filter="data.ok", max_runs_per_day=1)
    routine_id = uuid.UUID(str(created["id"]))
    filtered = accept_routine_event(
        store,
        routine_id=routine_id,
        source="webhook",
        idempotency_key="nope",
        envelope={"data": {"ok": False}},
    )
    assert filtered["status"] == "filtered"
    first = accept_routine_event(
        store,
        routine_id=routine_id,
        source="webhook",
        idempotency_key="same",
        envelope={"data": {"ok": True}},
    )
    again = accept_routine_event(
        store,
        routine_id=routine_id,
        source="webhook",
        idempotency_key="same",
        envelope={"data": {"ok": True}},
    )
    assert first["status"] == "accepted"
    assert again["status"] == "duplicate"
    limited = accept_routine_event(
        store,
        routine_id=routine_id,
        source="webhook",
        idempotency_key="other",
        envelope={"data": {"ok": True}},
    )
    assert limited["status"] == "rate_limited"
    store.routines[routine_id]["max_runs_per_day"] = 10
    store.routine_daily.clear()
    for index in range(5):
        accepted = accept_routine_event(
            store,
            routine_id=routine_id,
            source="manual",
            idempotency_key=f"fail-{index}",
            envelope={"type": "manual"},
        )
        event_id = uuid.UUID(str(accepted["event_id"]))
        prepare_routine_run(store, routine_id, event_id)
        run_id = store.routine_events[event_id]["run_id"]
        store.runs[run_id]["status"] = "failed"
        complete_routine_event(store, event_id, run_status="failed")
    assert store.routines[routine_id]["status"] == "paused"
    assert store.routines[routine_id]["paused_reason"] == "too_many_failures"


def test_inactive_owner_and_missing_delegation() -> None:
    store = _store()
    book = RoutineBook(store)
    created = _create(book)
    routine_id = uuid.UUID(str(created["id"]))
    owner = demo_id("admin")
    store.user_statuses[owner] = "suspended"
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="manual",
        idempotency_key="asleep",
        envelope={},
    )
    prepared = prepare_routine_run(store, routine_id, uuid.UUID(str(accepted["event_id"])))
    assert prepared["status"] == "needs_review"
    store.user_statuses[owner] = "active"
    store.routines[routine_id]["status"] = "active"
    store.reauth_users.add(owner)
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="manual",
        idempotency_key="reauth",
        envelope={},
    )
    prepared = prepare_routine_run(store, routine_id, uuid.UUID(str(accepted["event_id"])))
    assert prepared["reason"] == "owner_reauth_required"
    store.routines[routine_id]["status"] = "active"
    assert pause_for_owner(store, demo_id("tenant"), owner) >= 1
    assert store.routines[routine_id]["paused_reason"] == "owner_suspended"


def test_poll_respects_watermark_and_reconcile_repairs_drift() -> None:
    store = _store()
    book = RoutineBook(store)
    created = _create(
        book,
        trigger={"type": "db_change", "poll_interval_s": 60},
    )
    routine_id = uuid.UUID(str(created["id"]))
    store.routines[routine_id]["trigger_config"]["_pending"] = [
        {"idempotency_key": "1@t", "updated_at": "t", "id": "1"},
        {"idempotency_key": "1@t", "updated_at": "t2", "id": "1"},
    ]
    started = poll_routine_source(store, routine_id)
    assert len(started) == 1
    assert store.routines[routine_id]["trigger_config"]["_state"]["watermark"] == "t2"
    store.temporal_schedules.clear()
    store.routines[routine_id]["status"] = "active"
    store.routines[routine_id]["trigger_type"] = "schedule"
    store.routines[routine_id]["temporal_schedule_id"] = f"routine-{routine_id}"
    repaired = reconcile_schedules(store)
    assert repaired["repaired"] >= 1
    assert f"routine-{routine_id}" in store.temporal_schedules
    assert datetime.now(UTC).year >= 2026
    assert isinstance(new_id(), uuid.UUID)

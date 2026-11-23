"""A bundle or a pack can carry a routine. It arrives paused and approves nothing itself."""

from __future__ import annotations

import uuid
from typing import Any

from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService
from ar_domain.bundles.import_ import import_bundle
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.routines.book import RoutineBook
from ar_testing.demo import demo_store

AGENT = {
    "kind": "Agent",
    "metadata": {"slug": "page-reader", "name": "Page reader"},
    "spec": {"instructions": "Read the page you are given and say what it holds."},
}
ROUTINE = {
    "kind": "Routine",
    "metadata": {"name": "Morning read"},
    "spec": {
        "description": "Reads one page each morning.",
        "agent": "page-reader",
        "instructions": "Read the page and report.",
        "trigger": {"type": "schedule", "cron": "0 7 * * *", "timezone": "UTC"},
        "delivery": [{"type": "email", "preApproved": True, "config": {"to": "owner@example.org"}}],
        "budget": {
            "maxSteps": 24,
            "maxTokens": 200000,
            "maxCostMicros": 0,
            "maxWallClockS": 900,
            "maxToolCalls": 20,
            "maxParallelToolCalls": 2,
        },
        "maxRunsPerDay": 2,
    },
}


def _actor(*permissions: str) -> Actor:
    return Actor(
        demo_id("tenant"),
        demo_id("admin"),
        frozenset(permissions) if permissions else PERMISSION_KEYS,
        display_name="Dev Admin",
    )


def _bundle(*resources: dict[str, Any]) -> dict[str, Any]:
    return {"spec": {"resources": list(resources)}}


def _routine(store: Any, name: str = "Morning read") -> dict[str, Any] | None:
    for row in store.routines.values():
        if row.get("name") == name and row.get("tenant_id") == demo_id("tenant"):
            return row  # type: ignore[no-any-return]
    return None


def _by_kind(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["kind"]: row for row in result["results"]}


def test_a_routine_arrives_paused_with_its_agent_and_schedules_nothing() -> None:
    store = demo_store()
    before = set(getattr(store, "temporal_schedules", {}))
    standing = len(store.standing_approvals)
    # The routine is listed first: its agent is still made before it.
    done = _by_kind(import_bundle(store, _actor(), _bundle(ROUTINE, AGENT)))
    assert done["Agent"]["action"] == "create"
    assert done["Routine"]["action"] == "create"
    row = _routine(store)
    assert row is not None
    assert str(row["id"]) == done["Routine"]["id"]
    assert (row["status"], row["paused_reason"]) == ("paused", "imported")
    assert str(row["agent_id"]) == str(done["Agent"]["id"])
    assert row["trigger_config"]["cron"] == "0 7 * * *"
    assert row["budget"]["max_tool_calls"] == 20
    assert row["max_runs_per_day"] == 2
    assert set(getattr(store, "temporal_schedules", {})) == before
    # The bundle asked for its own delivery to be approved in advance. It is not.
    assert row["delivery"][0]["pre_approved"] is False
    assert row["delivery"][0]["config"] == {"to": "owner@example.org"}
    assert len(store.standing_approvals) == standing
    assert any(item["action"] == "routine.created" for item in store.audit_log)


def test_the_owner_turns_an_imported_routine_on() -> None:
    store = demo_store()
    import_bundle(store, _actor(), _bundle(AGENT, ROUTINE))
    row = _routine(store)
    assert row is not None
    resumed = RoutineBook(store).resume(_actor(), uuid.UUID(str(row["id"])))
    assert resumed["status"] == "active"
    assert store.temporal_schedules[row["temporal_schedule_id"]]["cron"] == "0 7 * * *"


def test_importing_again_leaves_the_routine_as_it_is() -> None:
    store = demo_store()
    import_bundle(store, _actor(), _bundle(AGENT, ROUTINE))
    row = _routine(store)
    assert row is not None
    row["instructions"] = "Edited here."
    again = _by_kind(import_bundle(store, _actor(), _bundle(AGENT, ROUTINE)))
    assert again["Routine"]["action"] == "unchanged"
    assert again["Routine"]["id"] == str(row["id"])
    assert row["instructions"] == "Edited here."
    assert sum(1 for item in store.routines.values() if item.get("name") == "Morning read") == 1


def test_a_plan_creates_nothing() -> None:
    store = demo_store()
    planned = _by_kind(import_bundle(store, _actor(), _bundle(AGENT, ROUTINE), dry_run=True))
    assert planned["Routine"]["action"] == "create"
    assert "id" not in planned["Routine"]
    assert _routine(store) is None


def test_a_routine_that_cannot_be_made_says_why() -> None:
    store = demo_store()
    orphan = _by_kind(import_bundle(store, _actor(), _bundle(ROUTINE)))["Routine"]
    assert orphan["action"] == "error"
    assert "page-reader" in orphan["errors"][0]["msg"]
    broken = {**ROUTINE, "spec": {**ROUTINE["spec"], "trigger": {"type": "sometimes"}}}  # type: ignore[dict-item]
    refused = _by_kind(import_bundle(store, _actor(), _bundle(AGENT, broken)))["Routine"]
    assert refused["action"] == "error"
    assert "trigger" in refused["errors"][0]["loc"]
    unnamed = {**ROUTINE, "metadata": {}}
    assert (
        _by_kind(import_bundle(store, _actor(), _bundle(unnamed)))["Routine"]["action"] == "error"
    )
    assert _routine(store) is None


def test_a_person_who_may_not_create_routines_gets_none() -> None:
    store = demo_store()
    limited = _actor("agents:create", "agents:read")
    done = _by_kind(import_bundle(store, limited, _bundle(AGENT, ROUTINE)))
    assert done["Agent"]["action"] == "create"
    assert done["Routine"]["action"] == "error"
    assert _routine(store) is None


def test_a_pack_installs_its_routine_paused() -> None:
    store = demo_store()
    manifest = {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "ContentPack",
        "metadata": {"id": "morning_read", "version": "1.0.0", "name": "Morning read"},
        "spec": {"resources": [AGENT, ROUTINE]},
    }
    installed = PackService(store).install(_actor(), manifest, signature=None, key_id=None)
    assert installed["status"] == "installed"
    actions = {row["kind"]: row["action"] for row in installed["import_results"]}  # type: ignore[union-attr]
    assert actions == {"Agent": "create", "Routine": "create"}
    row = _routine(store)
    assert row is not None
    assert row["status"] == "paused"

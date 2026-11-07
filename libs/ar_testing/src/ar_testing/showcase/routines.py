"""A weekly digest the routines page can open immediately."""

from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.chat.service import demo_id

if TYPE_CHECKING:
    import uuid

    from ar_domain.chat.service import ChatService


def seed_routines(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Insert the Monday digest once. Stable ids keep the row idempotent."""
    routine_id = demo_id("routine-weekly")
    if routine_id in store.routines:
        return
    agent = store.ensure_assistant(tenant_id, user_id)
    now = utcnow()
    store.routines[routine_id] = {
        "id": routine_id,
        "tenant_id": tenant_id,
        "name": "Weekly digest",
        "description": "Summarise the week and post it for the platform team.",
        "owner_user_id": user_id,
        "owner_name": "Admin",
        "run_as": "owner",
        "service_account_id": None,
        "agent_id": agent["id"],
        "agent_name": agent.get("name"),
        "agent_version_id": None,
        "instructions": "Write a short weekly digest for the platform team.",
        "trigger_type": "schedule",
        "trigger_config": {"cron": "0 9 * * 1", "timezone": "Asia/Kolkata", "jitter_s": 0},
        "event_filter": None,
        "delivery": [
            {"type": "conversation"},
            {"type": "slack", "channel": "#platform", "pre_approved": True, "config": {}},
        ],
        "budget": {
            "max_steps": 8,
            "max_tokens": 8000,
            "max_cost_micros": 0,
            "max_wall_clock_s": 300,
            "max_tool_calls": 4,
            "max_parallel_tool_calls": 1,
        },
        "max_runs_per_day": 4,
        "concurrency_policy": "skip",
        "status": "active",
        "paused_reason": None,
        "temporal_schedule_id": f"routine-{routine_id}",
        "webhook_path_token": None,
        "webhook_secret": "",
        "webhook_secret_previous": "",
        "webhook_secret_previous_until": None,
        "consecutive_failures": 0,
        "last_run_at": None,
        "next_run_at": None,
        "created_at": now,
        "updated_at": now,
    }
    store.temporal_schedules[f"routine-{routine_id}"] = {
        "cron": "0 9 * * 1",
        "timezone": "Asia/Kolkata",
        "overlap": "skip",
    }
    store.standing_approvals[demo_id("routine-weekly-standing")] = {
        "id": demo_id("routine-weekly-standing"),
        "tenant_id": tenant_id,
        "granted_by_user_id": user_id,
        "routine_id": routine_id,
        "tool_name": "delivery.slack_post",
        "expires_at": now,
        "revoked_at": None,
        "uses": 0,
    }

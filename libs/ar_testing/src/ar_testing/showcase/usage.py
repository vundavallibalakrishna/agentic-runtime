"""Seed a week of usage and a daily token quota the admin can see."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.chat.service import demo_id
from ar_domain.usage.logic import UsageRecord
from ar_domain.usage.service import UsageBook, note

if TYPE_CHECKING:
    import uuid

    from ar_domain.chat.service import ChatService

_DAYS = (4200, 7600, 3100, 9800, 6400, 11200, 24000)


def seed_usage(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Idempotent demo quota and daily totals. Chat stays under the limit."""
    _settings(store, tenant_id)
    store.user_emails[user_id] = "admin@dev.local"
    store.display_names[user_id] = "Dev Admin"
    quota_id = demo_id("quota-tokens")
    if quota_id not in store.quotas:
        now = utcnow()
        store.quotas[quota_id] = {
            "id": quota_id,
            "tenant_id": tenant_id,
            "scope_type": "user",
            "scope_id": user_id,
            "metric": "model_tokens",
            "period": "day",
            "limit_value": 100_000,
            "action": "block",
            "warn_at_pct": 80,
            "created_at": now,
            "updated_at": now,
            "implicit": False,
        }
    agent = store.ensure_assistant(tenant_id, user_id)
    agent_id = str(agent["id"])
    now = utcnow()
    for offset, quantity in enumerate(_DAYS):
        when = now - timedelta(days=len(_DAYS) - 1 - offset)
        _event(
            store, tenant_id, user_id, agent_id, when, "model_input_tokens", quantity, offset, "in"
        )
        _event(
            store,
            tenant_id,
            user_id,
            agent_id,
            when,
            "model_output_tokens",
            quantity // 2,
            offset,
            "out",
        )
    UsageBook(store).materialise()


def _event(  # noqa: PLR0917
    store: ChatService,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    agent_id: str,
    when: datetime,
    metric: str,
    quantity: int,
    offset: int,
    kind: str,
) -> None:
    note(
        store,
        UsageRecord(
            tenant_id=str(tenant_id),
            occurred_at=when,
            metric=metric,
            quantity=quantity,
            cost_micros=quantity * 5_000,
            dedupe_key=f"seed:{kind}:{offset}",
            user_id=str(user_id),
            agent_id=agent_id,
            model_alias="reasoning",
            source="seed",
        ),
    )


def _settings(store: ChatService, tenant_id: uuid.UUID) -> None:
    current = store.tenant_settings.get(tenant_id)
    merged = dict(current) if isinstance(current, dict) else {}
    merged.setdefault("billing_currency", "INR")
    merged.setdefault("timezone", "Asia/Kolkata")
    merged.setdefault("plan_key", "self_hosted")
    store.tenant_settings[tenant_id] = merged

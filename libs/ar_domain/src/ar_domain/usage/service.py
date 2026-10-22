"""Quota catalogue, enforcement and usage reports.

Spec: docs/03-specs/17-audit-usage-metering.md §2.
"""

import os
import threading
import uuid
from datetime import date, datetime, timedelta
from typing import Any, cast

from ar_common.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    ValidationFailedError,
)
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.identity.plan_limits import load_limits
from ar_domain.usage.logic import ZERO, UsageRecord, record_usage, rollup_daily
from ar_domain.usage.metrics import BLOCKS, EVENTS
from ar_domain.usage.quotas import (
    MemoryCounters,
    ValkeyCounters,
    applies,
    block_message,
    contribution,
    counter_key,
    in_scope,
    period_key,
    resets_at,
    subject_for,
    warn_key,
    zone,
)
from ar_domain.usage.reports import aggregate, normalise_groups, platform_csv, sum_rows, usage_csv

_SCOPES = frozenset({"tenant", "team", "user", "agent"})
_METRICS = frozenset({"cost_micros", "model_tokens", "runs", "sandbox_cpu_seconds", "tool_calls"})
_PERIODS = frozenset({"day", "month"})
_ACTIONS = frozenset({"block", "warn"})
_RUN_METRICS = ("runs", "cost_micros", "model_tokens")
_MODEL_METRICS = ("cost_micros", "model_tokens")
_MAX_RANGE_DAYS = 400


class UsageBook:
    """Quotas and reports for one process store."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.counters = counters_for(store)

    def list_quotas(self, actor: Any) -> list[dict[str, object]]:
        self._need(actor, "usage:read")
        rows = [self._view(actor, row) for row in self._all(actor.tenant_id)]
        rows.sort(key=lambda item: (str(item["metric"]), str(item["period"])))
        return rows

    def create(self, actor: Any, body: dict[str, object]) -> dict[str, object]:
        self._need(actor, "quotas:manage")
        row = self._new_row(actor, body)
        self._reject_duplicate(row)
        quota_id = cast("uuid.UUID", row["id"])
        self._table()[quota_id] = row
        self._audit(actor, "quota.created", quota_id, {"metric": row["metric"]})
        return self._view(actor, row)

    def update(self, actor: Any, quota_id: uuid.UUID, body: dict[str, object]) -> dict[str, object]:
        self._need(actor, "quotas:manage")
        row = self._owned(actor, quota_id)
        if "limit_value" in body:
            row["limit_value"] = _whole(body.get("limit_value"), minimum=0)
        if "action" in body:
            row["action"] = _choice(body.get("action"), _ACTIONS, "action")
        if "warn_at_pct" in body:
            row["warn_at_pct"] = _percent(body.get("warn_at_pct"))
        row["updated_at"] = utcnow()
        self._audit(actor, "quota.updated", quota_id, {"metric": row["metric"]})
        return self._view(actor, row)

    def delete(self, actor: Any, quota_id: uuid.UUID) -> None:
        self._need(actor, "quotas:manage")
        row = self._owned(actor, quota_id)
        self._table().pop(quota_id, None)
        self._audit(actor, "quota.deleted", quota_id, {"metric": row["metric"]})

    def assert_run(self, tenant_id: uuid.UUID, user_id: uuid.UUID, agent_id: object) -> None:
        self._assert(tenant_id, user_id, agent_id, _RUN_METRICS)

    def assert_model(self, tenant_id: uuid.UUID, user_id: object, agent_id: object) -> None:
        self._assert(tenant_id, _uuid(user_id), agent_id, _MODEL_METRICS)

    def assert_tool(self, tenant_id: uuid.UUID, user_id: object, agent_id: object) -> None:
        self._assert(tenant_id, _uuid(user_id), agent_id, ("tool_calls",))

    def assert_sandbox(self, tenant_id: uuid.UUID, user_id: object, agent_id: object) -> None:
        self._assert(tenant_id, _uuid(user_id), agent_id, ("sandbox_cpu_seconds",))

    def observe(self, record: UsageRecord) -> None:
        """Move counters after a new usage event. Warnings fire once per window."""
        EVENTS.labels(metric=record.metric, source=record.source or "api").inc()
        now = record.occurred_at
        for quota in self._all(record.tenant_id):
            amount = contribution(str(quota["metric"]), record)
            if amount <= 0 or not in_scope(quota, record):
                continue
            self._add(quota, record.user_id, amount, now)
            self._warn(quota, record.user_id, now)

    def materialise(self) -> None:
        """Rebuild ``usage_daily`` and set counters to those totals."""
        grouped: dict[str, list[UsageRecord]] = {}
        for record in self._events().values():
            grouped.setdefault(record.tenant_id, []).append(record)
        daily = self._daily()
        daily.clear()
        for tenant_id, records in grouped.items():
            for item in rollup_daily(records, self._zone(tenant_id)):
                daily[_daily_key(item)] = item
        self._reconcile(grouped)

    def summary(self, actor: Any, query: dict[str, str]) -> dict[str, object]:
        self._need(actor, "usage:read")
        self.materialise()
        groups = _groups(query.get("group_by", "day"))
        rows = self._filtered(str(actor.tenant_id), query)
        grouped = aggregate(rows, groups)
        return {
            "currency": self._currency(actor.tenant_id),
            "rows": grouped,
            "totals": sum_rows(grouped),
        }

    def export_csv(self, actor: Any, query: dict[str, str]) -> str:
        self._need(actor, "usage:read")
        self.materialise()
        rows = self._filtered(str(actor.tenant_id), query)
        return usage_csv(rows, self._currency(actor.tenant_id))

    def mine(self, actor: Any) -> dict[str, object]:
        """Current month for the signed-in user, plus the quotas that bind them."""
        self.materialise()
        today = utcnow().astimezone(zone(self._zone(actor.tenant_id))).date()
        start = today.replace(day=1)
        query = {"from": start.isoformat(), "to": today.isoformat(), "user_id": str(actor.user_id)}
        rows = self._filtered(str(actor.tenant_id), query)
        return {
            "currency": self._currency(actor.tenant_id),
            "from": start.isoformat(),
            "to": today.isoformat(),
            "totals": sum_rows(rows),
            "quotas": [self._mine_quota(actor, row) for row in self._binding(actor)],
        }

    def platform_summary(self, query: dict[str, str]) -> dict[str, object]:
        self.materialise()
        groups = _groups(query.get("group_by", "tenant"))
        rows = self._platform_rows(query)
        grouped = aggregate(rows, groups)
        return {"currency": _billing_currency(), "rows": grouped, "totals": sum_rows(grouped)}

    def platform_export(self, query: dict[str, str]) -> str:
        self.materialise()
        return platform_csv(self._platform_rows(query), _billing_currency())

    def _assert(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        agent_id: object,
        metrics: tuple[str, ...],
    ) -> None:
        now = utcnow()
        agent = str(agent_id) if agent_id else None
        user = str(user_id) if user_id else None
        teams = _teams(self.store, user_id)
        for quota in self._all(str(tenant_id)):
            if str(quota.get("metric")) not in metrics:
                continue
            if not applies(
                quota,
                tenant_id=str(tenant_id),
                user_id=user,
                team_ids=teams,
                agent_id=agent,
            ):
                continue
            used = self._read(quota, user, now)
            limit = _count(quota.get("limit_value"))
            if str(quota.get("action")) == "block" and used >= limit:
                self._blocked(quota, used, now)
            self._warn(quota, user, now)

    def _blocked(self, quota: dict[str, object], used: int, now: datetime) -> None:
        metric = str(quota["metric"])
        period = str(quota["period"])
        limit = _count(quota.get("limit_value"))
        BLOCKS.labels(metric=metric, scope=str(quota.get("scope_type"))).inc()
        detail = block_message(metric, period, limit)
        remember(
            self.store,
            tenant_id=quota.get("tenant_id"),
            actor_id="system",
            action="quota.exceeded",
            target_type="quota",
            target_id=quota.get("id"),
            detail={"metric": metric, "used": used, "limit": limit},
            outcome="failure",
        )
        self._event("quota.exceeded", quota, used)
        raise QuotaExceededError(
            detail,
            quota_id=str(quota["id"]),
            metric=metric,
            period=period,
            limit=limit,
            used=used,
            resets_at=resets_at(now, self._zone(quota.get("tenant_id")), period).isoformat(),
        )

    def _warn(self, quota: dict[str, object], user_id: str | None, now: datetime) -> None:
        limit = _count(quota.get("limit_value"))
        if limit <= 0:
            return
        used = self._read(quota, user_id, now)
        percent = _count(quota.get("warn_at_pct")) or 80
        if used * 100 < limit * percent:
            return
        period = period_key(now, self._zone(quota.get("tenant_id")), str(quota["period"]))
        subject = subject_for(quota, user_id)
        expires = resets_at(now, self._zone(quota.get("tenant_id")), str(quota["period"]))
        if not self.counters.claim(warn_key(str(quota["id"]), period, subject), expires):
            return
        self._notify(quota, user_id, used)
        self._event("quota.warning", quota, used)

    def _notify(self, quota: dict[str, object], user_id: str | None, used: int) -> None:
        title = block_message(
            str(quota["metric"]), str(quota["period"]), _count(quota.get("limit_value"))
        )
        targets = _admins(self.store)
        if str(quota.get("scope_type")) == "user" and user_id and user_id not in targets:
            targets.append(user_id)
        if not targets and user_id:
            targets.append(user_id)
        notifications = getattr(self.store, "notifications", None)
        if not isinstance(notifications, list):
            return
        for target in targets:
            notifications.append(
                {
                    "id": str(new_id()),
                    "tenant_id": str(quota.get("tenant_id")),
                    "user_id": target,
                    "kind": "quota_warning",
                    "title": "Quota warning",
                    "body": f"{title} Used {used:,}.",
                    "link": "/admin/quotas",
                    "read": False,
                }
            )

    def _event(self, topic: str, quota: dict[str, object], used: int) -> None:
        events = getattr(self.store, "domain_events", None)
        if not isinstance(events, list):
            return
        events.append(
            {
                "topic": topic,
                "payload": {
                    "quota_id": str(quota.get("id")),
                    "metric": str(quota.get("metric")),
                    "used": used,
                    "limit": _count(quota.get("limit_value")),
                },
                "at": utcnow().isoformat(),
            }
        )

    def _add(
        self, quota: dict[str, object], user_id: str | None, amount: int, now: datetime
    ) -> int:
        period = str(quota["period"])
        zone_name = self._zone(quota.get("tenant_id"))
        key = counter_key(
            str(quota["id"]),
            period_key(now, zone_name, period),
            subject_for(quota, user_id),
        )
        end = resets_at(now, zone_name, period) + timedelta(days=2)
        return self.counters.add(key, amount, end)

    def _read(self, quota: dict[str, object], user_id: str | None, now: datetime) -> int:
        period = str(quota["period"])
        zone_name = self._zone(quota.get("tenant_id"))
        key = counter_key(
            str(quota["id"]),
            period_key(now, zone_name, period),
            subject_for(quota, user_id),
        )
        return self.counters.read(key)

    def _reconcile(self, grouped: dict[str, list[UsageRecord]]) -> None:
        now = utcnow()
        for tenant_id, records in grouped.items():
            zone_name = self._zone(tenant_id)
            for quota in self._all(tenant_id):
                period = str(quota["period"])
                current = period_key(now, zone_name, period)
                end = resets_at(now, zone_name, period) + timedelta(days=2)
                buckets: dict[str, int] = {}
                for record in records:
                    if period_key(record.occurred_at, zone_name, period) != current:
                        continue
                    amount = contribution(str(quota["metric"]), record)
                    if amount <= 0 or not in_scope(quota, record):
                        continue
                    subject = subject_for(quota, record.user_id)
                    buckets[subject] = buckets.get(subject, 0) + amount
                if not buckets:
                    subject = subject_for(quota, None)
                    buckets[subject] = 0
                for subject, total in buckets.items():
                    key = counter_key(str(quota["id"]), current, subject)
                    self.counters.put(key, total, end)

    def _filtered(self, tenant_id: str, query: dict[str, str]) -> list[dict[str, object]]:
        start, end = _range(query)
        found: list[dict[str, object]] = []
        for item in self._daily().values():
            if item.tenant_id != tenant_id or not _in_range(item.day, start, end):
                continue
            row = self._report_row(item.tenant_id, item)
            if _match(row, query):
                found.append(row)
        return found

    def _platform_rows(self, query: dict[str, str]) -> list[dict[str, object]]:
        start, end = _range(query)
        found: list[dict[str, object]] = []
        for item in self._daily().values():
            if not _in_range(item.day, start, end):
                continue
            row = self._report_row(item.tenant_id, item)
            row["tenant_id"] = item.tenant_id
            row["plan_key"] = _plan_key(self.store, item.tenant_id)
            row["tenant"] = item.tenant_id
            found.append(row)
        return found

    def _report_row(self, tenant_id: str, item: Any) -> dict[str, object]:
        return {
            "day": item.day,
            "metric": item.metric,
            "user": self._user_label(item.user_id),
            "user_email": self._email(item.user_id),
            "team": self._team_label(item.team_id),
            "agent": self._agent_label(item.agent_id),
            "agent_slug": self._agent_slug(item.agent_id),
            "model": item.model_alias,
            "model_alias": item.model_alias,
            "quantity": item.quantity,
            "cost_micros": item.cost_micros,
            "user_id": "" if item.user_id == ZERO else item.user_id,
            "team_id": "" if item.team_id == ZERO else item.team_id,
            "agent_id": "" if item.agent_id == ZERO else item.agent_id,
            "tenant_id": tenant_id,
        }

    def _view(self, actor: Any, row: dict[str, object]) -> dict[str, object]:
        now = utcnow()
        user = str(actor.user_id)
        return {
            "id": str(row["id"]),
            "scope_type": row["scope_type"],
            "scope": _scope_view(self.store, row),
            "metric": row["metric"],
            "period": row["period"],
            "limit_value": _count(row.get("limit_value")),
            "action": row["action"],
            "warn_at_pct": _count(row.get("warn_at_pct")),
            "used": self._read(row, user, now),
            "resets_at": resets_at(
                now, self._zone(actor.tenant_id), str(row["period"])
            ).isoformat(),
            "implicit": bool(row.get("implicit")),
        }

    def _mine_quota(self, actor: Any, row: dict[str, object]) -> dict[str, object]:
        now = utcnow()
        return {
            "id": str(row["id"]),
            "metric": row["metric"],
            "period": row["period"],
            "limit": _count(row.get("limit_value")),
            "used": self._read(row, str(actor.user_id), now),
            "resets_at": resets_at(
                now, self._zone(actor.tenant_id), str(row["period"])
            ).isoformat(),
        }

    def _binding(self, actor: Any) -> list[dict[str, object]]:
        teams = set(getattr(actor, "team_ids", ()))
        return [
            row
            for row in self._all(str(actor.tenant_id))
            if applies(
                row,
                tenant_id=str(actor.tenant_id),
                user_id=str(actor.user_id),
                team_ids=teams,
                agent_id=None,
            )
        ]

    def _all(self, tenant_id: object) -> list[dict[str, object]]:
        found = [
            row for row in self._table().values() if str(row.get("tenant_id")) == str(tenant_id)
        ]
        found.extend(_implicit(tenant_id, load_limits(self.store, tenant_id).monthly_cost_micros))
        return found

    def _owned(self, actor: Any, quota_id: uuid.UUID) -> dict[str, object]:
        for item in _implicit(
            actor.tenant_id, load_limits(self.store, actor.tenant_id).monthly_cost_micros
        ):
            if item.get("id") == quota_id:
                raise ConflictError("plan quotas are managed with the plan")
        row = self._table().get(quota_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("quota not found")
        return row

    def _new_row(self, actor: Any, body: dict[str, object]) -> dict[str, object]:
        scope = _choice(body.get("scope_type"), _SCOPES, "scope_type")
        scope_id = _scope_id(scope, body.get("scope_id"))
        now = utcnow()
        return {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "scope_type": scope,
            "scope_id": scope_id,
            "metric": _choice(body.get("metric"), _METRICS, "metric"),
            "period": _choice(body.get("period"), _PERIODS, "period"),
            "limit_value": _whole(body.get("limit_value"), minimum=0),
            "action": _choice(body.get("action") or "block", _ACTIONS, "action"),
            "warn_at_pct": _percent(body.get("warn_at_pct") if "warn_at_pct" in body else 80),
            "created_at": now,
            "updated_at": now,
            "implicit": False,
        }

    def _reject_duplicate(self, row: dict[str, object]) -> None:
        for other in self._table().values():
            same = (
                other.get("tenant_id") == row["tenant_id"]
                and other.get("scope_type") == row["scope_type"]
                and _same_id(other.get("scope_id"), row.get("scope_id"))
                and other.get("metric") == row["metric"]
                and other.get("period") == row["period"]
            )
            if same:
                raise ConflictError("a quota with that scope already exists")

    def _audit(
        self, actor: Any, action: str, quota_id: uuid.UUID, detail: dict[str, object]
    ) -> None:
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action=action,
            target_type="quota",
            target_id=quota_id,
            detail=detail,
        )

    def _need(self, actor: Any, permission: str) -> None:
        if not actor.has(permission):
            raise ForbiddenError(f"missing permission {permission}")

    def _table(self) -> dict[uuid.UUID, dict[str, object]]:
        table = getattr(self.store, "quotas", None)
        if not isinstance(table, dict):
            table = {}
            self.store.quotas = table
        return table

    def _events(self) -> dict[tuple[str, str], UsageRecord]:
        usage = getattr(self.store, "usage", None)
        if isinstance(usage, dict):
            return usage
        return {}

    def _daily(self) -> dict[tuple[str, ...], Any]:
        daily = getattr(self.store, "usage_daily", None)
        if not isinstance(daily, dict):
            daily = {}
            self.store.usage_daily = daily
        return daily

    def _zone(self, tenant_id: object) -> str:
        settings = _settings(self.store, tenant_id)
        name = settings.get("timezone")
        if isinstance(name, str) and name:
            return name
        return "Asia/Kolkata"

    def _currency(self, tenant_id: object) -> str:
        settings = _settings(self.store, tenant_id)
        name = settings.get("billing_currency")
        if isinstance(name, str) and name:
            return name
        return _billing_currency()

    def _email(self, user_id: str) -> str:
        if user_id == ZERO:
            return ""
        emails = getattr(self.store, "user_emails", {})
        if not isinstance(emails, dict):
            return ""
        parsed = _as_uuid(user_id)
        if parsed in emails:
            return str(emails[parsed])
        if user_id in emails:
            return str(emails[user_id])
        return ""

    def _user_label(self, user_id: str) -> str:
        email = self._email(user_id)
        if email:
            return email
        names = getattr(self.store, "display_names", {})
        if isinstance(names, dict) and _as_uuid(user_id) in names:
            return str(names[_as_uuid(user_id)])
        return ""

    def _team_label(self, team_id: str) -> str:
        if team_id == ZERO:
            return ""
        roster = getattr(self.store, "team_roster", {})
        row = roster.get(_as_uuid(team_id)) if isinstance(roster, dict) else None
        if isinstance(row, dict) and row.get("name"):
            return str(row["name"])
        return ""

    def _agent_label(self, agent_id: str) -> str:
        agent = self._agent(agent_id)
        if agent is None:
            return ""
        return str(agent.get("name") or agent.get("slug") or "")

    def _agent_slug(self, agent_id: str) -> str:
        agent = self._agent(agent_id)
        if agent is None:
            return ""
        return str(agent.get("slug") or "")

    def _agent(self, agent_id: str) -> dict[str, object] | None:
        if agent_id == ZERO:
            return None
        agents = getattr(self.store, "agents", {})
        row = agents.get(_as_uuid(agent_id)) if isinstance(agents, dict) else None
        if isinstance(row, dict):
            return row
        return None


def note(store: Any, record: UsageRecord) -> bool:
    """Insert one usage event and spend the quotas it matches."""
    usage = getattr(store, "usage", None)
    if not isinstance(usage, dict):
        return False
    if not record_usage(usage, record):
        return False
    UsageBook(store).observe(record)
    return True


def counters_for(store: Any) -> MemoryCounters | ValkeyCounters:
    """Reuse the counter object hung on the store."""
    current = getattr(store, "_quota_ports", None)
    if isinstance(current, (MemoryCounters, ValkeyCounters)):
        return current
    slots = getattr(store, "quota_counters", None)
    if not isinstance(slots, dict):
        slots = {}
        store.quota_counters = slots
    lock = getattr(store, "quota_lock", None)
    if not isinstance(lock, threading.Lock):
        lock = threading.Lock()
        store.quota_lock = lock
    memory = MemoryCounters(slots, lock)
    client = getattr(store, "valkey_client", None)
    port: MemoryCounters | ValkeyCounters = memory
    if client is not None:
        port = ValkeyCounters(client, memory)
    store._quota_ports = port
    return port


def _implicit(tenant_id: object, monthly_cost: int | None) -> list[dict[str, object]]:
    if monthly_cost is None:
        return []
    quota_id = uuid.uuid5(uuid.UUID(str(tenant_id)), "monthly-cost")
    return [
        {
            "id": quota_id,
            "tenant_id": uuid.UUID(str(tenant_id)),
            "scope_type": "tenant",
            "scope_id": None,
            "metric": "cost_micros",
            "period": "month",
            "limit_value": monthly_cost,
            "action": "block",
            "warn_at_pct": 80,
            "implicit": True,
        }
    ]


def _scope_view(store: Any, row: dict[str, object]) -> dict[str, str] | None:
    scope_id = row.get("scope_id")
    if scope_id is None:
        return None
    name = ""
    scope = str(row.get("scope_type"))
    if scope == "user":
        emails = getattr(store, "user_emails", {})
        names = getattr(store, "display_names", {})
        name = str(emails.get(str(scope_id)) or names.get(scope_id) or "")
    elif scope == "agent":
        agents = getattr(store, "agents", {})
        agent = agents.get(scope_id) if isinstance(agents, dict) else None
        if isinstance(agent, dict):
            name = str(agent.get("name") or "")
    elif scope == "team":
        roster = getattr(store, "team_roster", {})
        team = roster.get(scope_id) if isinstance(roster, dict) else None
        if isinstance(team, dict):
            name = str(team.get("name") or "")
    return {"id": str(scope_id), "name": name}


def _teams(store: Any, user_id: uuid.UUID | None) -> set[str]:
    if user_id is None:
        return set()
    roster = getattr(store, "team_roster", {})
    if not isinstance(roster, dict):
        return set()
    found: set[str] = set()
    for team_id, row in roster.items():
        if not isinstance(row, dict):
            continue
        members = row.get("members")
        if isinstance(members, list) and str(user_id) in {str(item) for item in members}:
            found.add(str(team_id))
    return found


def _admins(store: Any) -> list[str]:
    roles = getattr(store, "user_roles", {})
    if not isinstance(roles, dict):
        return []
    found: list[str] = []
    for user_id, names in roles.items():
        if isinstance(names, (set, frozenset, list, tuple)) and "tenant_admin" in names:
            found.append(str(user_id))
    return found


def _settings(store: Any, tenant_id: object) -> dict[str, object]:
    settings = getattr(store, "tenant_settings", {})
    if not isinstance(settings, dict):
        return {}
    raw = settings.get(tenant_id)
    if isinstance(raw, dict):
        return raw
    text = str(tenant_id)
    for key, value in settings.items():
        if str(key) == text and isinstance(value, dict):
            return value
    return {}


def _plan_key(store: Any, tenant_id: str) -> str:
    key = _settings(store, tenant_id).get("plan_key")
    if isinstance(key, str) and key:
        return key
    return "self_hosted"


def _billing_currency() -> str:
    return os.environ.get("AR_BILLING_CURRENCY", "INR")


def _daily_key(item: Any) -> tuple[str, ...]:
    return (
        item.tenant_id,
        item.day,
        item.metric,
        item.user_id,
        item.team_id,
        item.agent_id,
        item.model_alias,
    )


def _groups(raw: str) -> tuple[str, ...]:
    try:
        return normalise_groups(raw)
    except ValueError as exc:
        raise ValidationFailedError(
            "group_by must be up to two of day, metric, agent, user, team, model, tenant"
        ) from exc


def _range(query: dict[str, str]) -> tuple[date, date]:
    today = utcnow().date()
    start = _date(query.get("from")) or (today - timedelta(days=30))
    end = _date(query.get("to")) or today
    if end < start or (end - start).days > _MAX_RANGE_DAYS:
        raise ValidationFailedError("the date range must be within 400 days")
    return start, end


def _date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationFailedError("dates must be YYYY-MM-DD") from exc


def _in_range(day: str, start: date, end: date) -> bool:
    try:
        found = date.fromisoformat(day)
    except ValueError:
        return False
    return start <= found <= end


def _match(row: dict[str, object], query: dict[str, str]) -> bool:
    if query.get("metric") and row.get("metric") != query["metric"]:
        return False
    if query.get("agent_id") and row.get("agent_id") != query["agent_id"]:
        return False
    if query.get("user_id") and row.get("user_id") != query["user_id"]:
        return False
    return not (query.get("team_id") and row.get("team_id") != query["team_id"])


def _choice(value: object, allowed: frozenset[str], name: str) -> str:
    text = str(value or "")
    if text not in allowed:
        raise ValidationFailedError(f"{name} is not valid")
    return text


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _whole(value: object, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationFailedError("limit_value must be zero or greater")
    return value


def _percent(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValidationFailedError("warn_at_pct must be between 1 and 100")
    return value


def _scope_id(scope: str, value: object) -> uuid.UUID | None:
    if scope == "tenant":
        if value not in (None, ""):
            raise ValidationFailedError("a tenant quota has no scope id")
        return None
    if value in (None, ""):
        if scope == "user":
            return None
        raise ValidationFailedError("scope_id is required")
    parsed = _uuid(value)
    if parsed is None:
        raise ValidationFailedError("scope_id must be a uuid")
    return parsed


def _same_id(left: object, right: object) -> bool:
    if left is None and right is None:
        return True
    return left is not None and right is not None and str(left) == str(right)


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _as_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        return uuid.UUID(int=0)

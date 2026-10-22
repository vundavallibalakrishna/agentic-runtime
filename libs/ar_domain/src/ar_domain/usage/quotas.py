"""Quota windows, counter keys and applicability.

Spec: docs/03-specs/17-audit-usage-metering.md §2.1-§2.2.
Counters use ``ar:q:{quota_id}:{period}``. An each-user quota adds the user id
so people do not share one bucket (OQ-43).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    import threading

    from ar_domain.usage.logic import UsageRecord

_TOKEN_METRICS = frozenset({"model_input_tokens", "model_output_tokens"})
_LABELS = {
    "model_tokens": "token",
    "cost_micros": "spend",
    "runs": "run",
    "sandbox_cpu_seconds": "sandbox",
    "tool_calls": "tool-call",
}


def zone(name: str) -> ZoneInfo:
    """Tenant timezone. An unknown name falls back to Asia/Kolkata."""
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Kolkata")


def period_key(moment: datetime, timezone_name: str, period: str) -> str:
    """Day ``YYYY-MM-DD`` or month ``YYYY-MM`` in the tenant timezone."""
    local = moment.astimezone(zone(timezone_name))
    if period == "month":
        return local.strftime("%Y-%m")
    return local.date().isoformat()


def resets_at(moment: datetime, timezone_name: str, period: str) -> datetime:
    """First instant of the next day or month, in UTC."""
    local = moment.astimezone(zone(timezone_name))
    if period == "month":
        year = local.year + (1 if local.month == 12 else 0)
        month = 1 if local.month == 12 else local.month + 1
        start = local.replace(
            year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        start = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def counter_key(quota_id: str, period: str, subject: str = "") -> str:
    """Valkey key for one quota window."""
    if subject:
        return f"ar:q:{quota_id}:{subject}:{period}"
    return f"ar:q:{quota_id}:{period}"


def warn_key(quota_id: str, period: str, subject: str = "") -> str:
    """Set-once key so a threshold notifies one time per window."""
    if subject:
        return f"ar:qwarn:{quota_id}:{subject}:{period}"
    return f"ar:qwarn:{quota_id}:{period}"


def subject_for(quota: dict[str, object], user_id: str | None) -> str:
    """Each-user quotas keep a counter per person. Other scopes share one."""
    if str(quota.get("scope_type")) == "user" and quota.get("scope_id") is None:
        return user_id or ""
    return ""


def contribution(metric: str, record: UsageRecord) -> int:
    """How much of ``record`` counts against a quota metric."""
    if metric == "model_tokens" and record.metric in _TOKEN_METRICS:
        return record.quantity
    if metric == "cost_micros":
        return record.cost_micros
    if metric == record.metric:
        return record.quantity
    return 0


def in_scope(quota: dict[str, object], record: UsageRecord) -> bool:  # noqa: PLR0911
    """Whether this event spends the quota."""
    if record.tenant_id != str(quota.get("tenant_id")):
        return False
    scope = str(quota.get("scope_type"))
    scope_id = quota.get("scope_id")
    if scope == "tenant":
        return True
    if scope == "team":
        return record.team_id is not None and record.team_id == str(scope_id)
    if scope == "agent":
        return record.agent_id is not None and record.agent_id == str(scope_id)
    if scope == "user":
        if scope_id is None:
            return record.user_id is not None
        return record.user_id == str(scope_id)
    return False


def applies(  # noqa: PLR0911
    quota: dict[str, object],
    *,
    tenant_id: str,
    user_id: str | None,
    team_ids: set[str],
    agent_id: str | None,
) -> bool:
    """Whether this quota binds the caller about to spend it."""
    if str(quota.get("tenant_id")) != tenant_id:
        return False
    scope = str(quota.get("scope_type"))
    scope_id = quota.get("scope_id")
    if scope == "tenant":
        return True
    if scope == "team":
        return scope_id is not None and str(scope_id) in team_ids
    if scope == "agent":
        return agent_id is not None and str(scope_id) == agent_id
    if scope == "user":
        if user_id is None:
            return False
        return scope_id is None or str(scope_id) == user_id
    return False


def block_message(metric: str, period: str, limit: int) -> str:
    """Sentence shown in chat and on the problem body."""
    label = _LABELS.get(metric, metric.replace("_", " "))
    window = "today" if period == "day" else "this month"
    return (
        f"Quota reached. The {label} quota for {window} is {limit:,}. "
        "This run is blocked until the quota resets."
    )


class MemoryCounters:
    """Process counters with the Valkey key scheme. OQ-43."""

    def __init__(self, slots: dict[str, tuple[int, datetime]], lock: threading.Lock) -> None:
        self.slots = slots
        self.lock = lock

    def add(self, key: str, amount: int, expires: datetime) -> int:
        with self.lock:
            current = self._live(key)
            updated = current + amount
            self.slots[key] = (updated, expires)
            return updated

    def read(self, key: str) -> int:
        with self.lock:
            return self._live(key)

    def put(self, key: str, value: int, expires: datetime) -> None:
        with self.lock:
            self.slots[key] = (value, expires)

    def claim(self, key: str, expires: datetime) -> bool:
        """SET NX. True only the first time the key is claimed in this window."""
        with self.lock:
            if self._live(key) > 0:
                return False
            self.slots[key] = (1, expires)
            return True

    def _live(self, key: str) -> int:
        found = self.slots.get(key)
        if found is None:
            return 0
        value, expires = found
        if expires <= datetime.now(UTC):
            return 0
        return value


class ValkeyCounters:
    """Redis INCRBY / SET / SET NX. The first connection error fails open."""

    def __init__(self, client: Any, memory: MemoryCounters) -> None:
        self.client = client
        self.memory = memory
        self.open = False

    def add(self, key: str, amount: int, expires: datetime) -> int:
        if self.open:
            return self._open_add(key, amount, expires)
        try:
            value = int(self.client.incrby(key, amount))
            self.client.expire(key, _ttl(expires))
        except Exception:  # noqa: BLE001 - Valkey loss fails open
            self.open = True
            return self._open_add(key, amount, expires)
        return value

    def read(self, key: str) -> int:
        if self.open:
            from ar_domain.usage.metrics import BYPASS  # noqa: PLC0415

            BYPASS.inc()
            return self.memory.read(key)
        try:
            raw = self.client.get(key)
        except Exception:  # noqa: BLE001 - Valkey loss fails open
            self.open = True
            from ar_domain.usage.metrics import BYPASS  # noqa: PLC0415

            BYPASS.inc()
            return self.memory.read(key)
        if raw is None:
            return 0
        return int(raw)

    def put(self, key: str, value: int, expires: datetime) -> None:
        if self.open:
            self.memory.put(key, value, expires)
            return
        try:
            self.client.set(key, value, ex=_ttl(expires))
        except Exception:  # noqa: BLE001 - Valkey loss fails open
            self.open = True
            self.memory.put(key, value, expires)

    def claim(self, key: str, expires: datetime) -> bool:
        if self.open:
            return self.memory.claim(key, expires)
        try:
            claimed = bool(self.client.set(key, 1, nx=True, ex=_ttl(expires)))
        except Exception:  # noqa: BLE001 - Valkey loss fails open
            self.open = True
            return self.memory.claim(key, expires)
        return claimed

    def _open_add(self, key: str, amount: int, expires: datetime) -> int:
        from ar_domain.usage.metrics import BYPASS  # noqa: PLC0415

        BYPASS.inc()
        return self.memory.add(key, amount, expires)


def _ttl(expires: datetime) -> int:
    seconds = int((expires - datetime.now(UTC)).total_seconds())
    return max(seconds, 60)

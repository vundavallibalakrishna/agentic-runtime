"""Usage recording and daily rollup. Spec: docs/03-specs/17-audit-usage-metering.md §2."""

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from zoneinfo import ZoneInfo

ZERO = "00000000-0000-0000-0000-000000000000"


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """One metered quantity. ``dedupe_key`` is unique per tenant."""

    tenant_id: str
    occurred_at: datetime
    metric: str
    quantity: int
    cost_micros: int
    dedupe_key: str
    user_id: str | None = None
    team_id: str | None = None
    agent_id: str | None = None
    model_alias: str = ""
    source: str = "api"


@dataclass(frozen=True, slots=True)
class DailyUsage:
    """One ``usage_daily`` row."""

    tenant_id: str
    day: str
    metric: str
    user_id: str
    team_id: str
    agent_id: str
    model_alias: str
    quantity: int
    cost_micros: int


def record_usage(existing: dict[tuple[str, str], UsageRecord], item: UsageRecord) -> bool:
    """Insert ``item`` unless ``(tenant_id, dedupe_key)`` was already recorded."""
    key = (item.tenant_id, item.dedupe_key)
    if key in existing:
        return False
    existing[key] = item
    return True


def rollup_daily(records: list[UsageRecord], timezone_name: str) -> list[DailyUsage]:
    """Sum records into tenant-local days. Repeating the call is idempotent."""
    zone = ZoneInfo(timezone_name)
    totals: dict[tuple[str, str, str, str, str, str, str], list[int]] = {}
    for item in records:
        local = item.occurred_at.astimezone(zone)
        day = local.date().isoformat()
        key = (
            item.tenant_id,
            day,
            item.metric,
            item.user_id or ZERO,
            item.team_id or ZERO,
            item.agent_id or ZERO,
            item.model_alias,
        )
        bucket = totals.setdefault(key, [0, 0])
        bucket[0] += item.quantity
        bucket[1] += item.cost_micros
    return [
        DailyUsage(
            tenant_id=key[0],
            day=key[1],
            metric=key[2],
            user_id=key[3],
            team_id=key[4],
            agent_id=key[5],
            model_alias=key[6],
            quantity=values[0],
            cost_micros=values[1],
        )
        for key, values in sorted(totals.items())
    ]


def gateway_dedupe_keys(request_id: str) -> tuple[str, str, str]:
    """Usage keys emitted once per model-gateway request."""
    return (
        f"mg:{request_id}:in",
        f"mg:{request_id}:out",
        f"mg:{request_id}:cached",
    )

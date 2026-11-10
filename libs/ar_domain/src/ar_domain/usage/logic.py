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
    run_id: str | None = None
    model_id: str | None = None
    tool_id: str | None = None
    routine_id: str | None = None
    api_key_id: str | None = None


def model_cost_micros(
    tokens_in: int, tokens_out: int, *, price_in_per_mtok: int, price_out_per_mtok: int
) -> int:
    """Cost in micros of the tenant currency from per-million-token prices (spec 17 §2)."""
    return (
        max(0, tokens_in) * max(0, price_in_per_mtok)
        + max(0, tokens_out) * max(0, price_out_per_mtok)
    ) // 1_000_000


def usage_rows_to_flush(
    usage: dict[tuple[str, str], UsageRecord], flushed: set[tuple[str, str]], tenant_id: object
) -> list[tuple[tuple[str, str], UsageRecord]]:
    """Records for the bound tenant that Postgres has not seen yet, oldest first."""
    wanted = str(tenant_id)
    rows = [
        (key, item)
        for key, item in usage.items()
        if key not in flushed and item.tenant_id == wanted
    ]
    rows.sort(key=lambda pair: pair[1].occurred_at)
    return rows


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
    api_key_id: str = ZERO


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
    totals: dict[tuple[str, str, str, str, str, str, str, str], list[int]] = {}
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
            item.api_key_id or ZERO,
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
            api_key_id=key[7],
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

"""Usage rollup. Spec: docs/03-specs/17-audit-usage-metering.md §2.3.

The Temporal schedule calls :func:`rollup`. Repeating a window replaces totals.
"""

from ar_domain.usage.logic import DailyUsage, UsageRecord, rollup_daily


def rollup(records: list[UsageRecord], timezone_name: str) -> list[DailyUsage]:
    """Idempotent daily totals in the tenant timezone."""
    return rollup_daily(records, timezone_name)

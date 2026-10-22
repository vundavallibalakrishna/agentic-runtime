"""Quota counters. Spec: docs/03-specs/17-audit-usage-metering.md §5."""

from prometheus_client import Counter

BLOCKS = Counter(
    "ar_quota_blocks_total",
    "Calls rejected because a block quota was already spent",
    ["metric", "scope"],
)
BYPASS = Counter(
    "ar_quota_check_bypass_total",
    "Quota checks allowed because the counter store was unavailable",
)
EVENTS = Counter(
    "ar_usage_events_total",
    "Usage events recorded",
    ["metric", "source"],
)

"""Channel counters. Spec: docs/03-specs/16-channels.md §10."""

from prometheus_client import Counter, Histogram

INBOUND = Counter(
    "ar_channel_inbound_total",
    "Inbound channel messages",
    ["kind", "result"],
)
REPLY_LATENCY = Histogram(
    "ar_channel_reply_latency_seconds",
    "Time from inbound to the first visible reply",
    ["kind"],
)
OUTBOUND = Counter(
    "ar_channel_outbound_total",
    "Outbound channel sends",
    ["kind", "result"],
)
RATE_LIMITED = Counter(
    "ar_channel_rate_limited_total",
    "Channel sends delayed by a provider rate limit",
    ["kind"],
)
LINK_REQUIRED = Counter(
    "ar_channel_link_required_total",
    "Inbound messages from people who are not linked",
    ["kind"],
)

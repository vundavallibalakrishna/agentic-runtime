"""Sandbox metrics. Spec: docs/03-specs/12-sandbox-manager.md §9."""

from prometheus_client import Counter, Gauge, Histogram

from ar_common.metrics import REGISTRY

SANDBOXES = Gauge(
    "ar_sandboxes",
    "Live sandboxes by status.",
    ("status",),
    registry=REGISTRY,
)
ENSURE_SECONDS = Histogram(
    "ar_sandbox_ensure_seconds",
    "Time to make a sandbox ready.",
    registry=REGISTRY,
)
EXEC_SECONDS = Histogram(
    "ar_sandbox_exec_seconds",
    "Time spent in sandbox.exec.",
    registry=REGISTRY,
)
CPU_SECONDS = Counter(
    "ar_sandbox_cpu_seconds_total",
    "CPU seconds charged to sandboxes.",
    registry=REGISTRY,
)
EGRESS_DENIED = Counter(
    "ar_sandbox_egress_denied_total",
    "Egress checks that denied a host.",
    registry=REGISTRY,
)
SNAPSHOT_BYTES = Histogram(
    "ar_sandbox_snapshot_bytes",
    "Bytes stored in a workspace snapshot.",
    registry=REGISTRY,
)
WARM_POOL = Gauge(
    "ar_sandbox_warm_pool_available",
    "Warm sandboxes waiting for a claim.",
    ("template",),
    registry=REGISTRY,
)

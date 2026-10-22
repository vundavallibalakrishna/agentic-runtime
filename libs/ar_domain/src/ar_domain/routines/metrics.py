"""Routine metrics. Spec: docs/03-specs/15-routines-triggers.md §8."""

from prometheus_client import Counter, Gauge

from ar_common.metrics import REGISTRY

EVENTS = Counter(
    "ar_routine_events_total",
    "Routine events by source and status.",
    ("source", "status"),
    registry=REGISTRY,
)
RUNS = Counter(
    "ar_routine_runs_total",
    "Routine runs by terminal status.",
    ("status",),
    registry=REGISTRY,
)
DELIVERY = Counter(
    "ar_routine_delivery_total",
    "Delivery attempts by target and result.",
    ("target", "result"),
    registry=REGISTRY,
)
ACTIVE = Gauge(
    "ar_routines",
    "Routines by status.",
    ("status",),
    registry=REGISTRY,
)

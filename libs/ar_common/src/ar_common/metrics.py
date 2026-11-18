"""Prometheus registry helpers. Spec: docs/03-specs/18-observability-eval.md §1."""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)

PLATFORM_DB_DENY_UNRESOLVED = Gauge(
    "ar_platform_db_deny_unresolved",
    "1 when a platform database deny name has never resolved.",
    registry=REGISTRY,
)

REQUESTS = Counter(
    "ar_http_requests_total",
    "HTTP requests handled by this process.",
    ("service", "status"),
    registry=REGISTRY,
)


def render_metrics() -> bytes:
    """Render the process registry in Prometheus text format."""
    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    """Return the Prometheus exposition content type."""
    return str(CONTENT_TYPE_LATEST)

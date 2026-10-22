"""Memory metrics. Spec: docs/03-specs/11-memory.md §7."""

from prometheus_client import Counter, Gauge, Histogram

from ar_common.metrics import REGISTRY

RECALL_SECONDS = Histogram(
    "ar_memory_recall_seconds",
    "Memory recall latency, excluding the embedding call.",
    registry=REGISTRY,
)
RECALLED_FACTS = Histogram(
    "ar_memory_recalled_facts",
    "Facts injected into one recall.",
    registry=REGISTRY,
)
EXTRACTION_OPS = Counter(
    "ar_memory_extraction_ops_total",
    "Memory extraction operations by outcome.",
    ("op", "result"),
    registry=REGISTRY,
)
FACTS = Gauge(
    "ar_memory_facts",
    "Active memory facts by scope.",
    ("scope",),
    registry=REGISTRY,
)
PENDING_REVIEW = Gauge(
    "ar_memory_pending_review",
    "Memory facts waiting for review.",
    registry=REGISTRY,
)
COMPACTIONS = Counter(
    "ar_runtime_compactions_total",
    "Context compactions performed by the runtime.",
    registry=REGISTRY,
)

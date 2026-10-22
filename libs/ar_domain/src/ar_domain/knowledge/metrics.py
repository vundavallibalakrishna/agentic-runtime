"""Knowledge metrics. Spec: docs/03-specs/10-knowledge.md §13."""

from prometheus_client import Counter, Gauge, Histogram

from ar_common.metrics import REGISTRY

INGEST_DOCUMENTS = Counter(
    "ar_ingest_documents_total",
    "Documents finished by the ingest pipeline.",
    ("kind", "result"),
    registry=REGISTRY,
)
INGEST_STAGE = Histogram(
    "ar_ingest_stage_seconds",
    "Seconds spent in an ingest stage.",
    ("stage",),
    registry=REGISTRY,
)
INGEST_QUEUE = Gauge(
    "ar_ingest_queue_depth",
    "Ingest jobs that are still queued.",
    registry=REGISTRY,
)
SEARCH_SECONDS = Histogram(
    "ar_knowledge_search_seconds",
    "Knowledge search latency by stage.",
    ("stage",),
    registry=REGISTRY,
)
SEARCH_HITS = Histogram(
    "ar_knowledge_search_hits",
    "Hits returned by a knowledge search.",
    registry=REGISTRY,
)
UNANSWERABLE = Counter(
    "ar_knowledge_unanswerable_total",
    "Searches that were below the answerability threshold.",
    registry=REGISTRY,
)
ACL_LAG = Gauge(
    "ar_acl_sync_lag_seconds",
    "Seconds since the last ACL sync.",
    ("source",),
    registry=REGISTRY,
)
LATE_DENIED = Counter(
    "ar_late_verification_denied_total",
    "High-sensitivity hits dropped by late verification.",
    registry=REGISTRY,
)
STORE_SECONDS = Histogram(
    "ar_retrieval_store_seconds",
    "Retrieval store operation latency.",
    ("backend", "operation"),
    registry=REGISTRY,
)
STORE_ERRORS = Counter(
    "ar_retrieval_store_errors_total",
    "Retrieval store errors.",
    ("backend", "operation", "kind"),
    registry=REGISTRY,
)
COUNT_DRIFT = Gauge(
    "ar_retrieval_store_count_drift",
    "Chunks present in Postgres but missing from the retrieval store.",
    ("collection",),
    registry=REGISTRY,
)

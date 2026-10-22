"""Policy and approval metrics. Spec: docs/03-specs/09-policy-approvals.md §8."""

from prometheus_client import Counter, Histogram

from ar_common.metrics import REGISTRY

DECISIONS = Counter(
    "ar_policy_decisions_total",
    "Policy decisions by outcome and risk class.",
    ("decision", "risk"),
    registry=REGISTRY,
)
EVAL_SECONDS = Histogram(
    "ar_policy_eval_seconds",
    "Time spent evaluating a policy decision.",
    registry=REGISTRY,
)
FALLBACK = Counter(
    "ar_policy_fallback_total",
    "Decisions taken by the fallback evaluator.",
    registry=REGISTRY,
)
APPROVALS_CREATED = Counter(
    "ar_approvals_created_total",
    "Approvals created, by risk class.",
    ("risk",),
    registry=REGISTRY,
)
APPROVALS_RESOLVED = Counter(
    "ar_approvals_resolved_total",
    "Approvals resolved, by status and channel.",
    ("status", "channel"),
    registry=REGISTRY,
)
DECISION_SECONDS = Histogram(
    "ar_approval_time_to_decision_seconds",
    "Seconds from approval creation to a terminal status.",
    registry=REGISTRY,
)
BUNDLE_SECONDS = Histogram(
    "ar_opa_bundle_build_seconds",
    "Time spent building the OPA bundle.",
    registry=REGISTRY,
)

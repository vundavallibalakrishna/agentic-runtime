"""Evaluation metrics. Spec: docs/03-specs/18-observability-eval.md §5."""

from prometheus_client import Counter, Gauge, Histogram

from ar_common.metrics import REGISTRY

RUNS = Counter(
    "ar_eval_runs_total",
    "Evaluation runs by status and trigger.",
    ("status", "trigger"),
    registry=REGISTRY,
)
CASE_SECONDS = Histogram(
    "ar_eval_case_seconds",
    "Time spent scoring one evaluation case.",
    registry=REGISTRY,
)
PASS_RATE = Gauge(
    "ar_eval_pass_rate",
    "Pass rate of the latest run for a suite.",
    ("suite",),
    registry=REGISTRY,
)
JUDGE_CALLS = Counter(
    "ar_eval_judge_calls_total",
    "Judge and refusal grader calls.",
    registry=REGISTRY,
)

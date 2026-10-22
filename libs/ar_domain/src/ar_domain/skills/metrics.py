"""Skill and subagent metrics. Spec: docs/03-specs/14-skills.md §6, spec 07 §11."""

from prometheus_client import Counter

from ar_common.metrics import REGISTRY

SKILL_LOADS = Counter(
    "ar_skill_loads_total",
    "Times a published skill was loaded into a run.",
    ("skill",),
    registry=REGISTRY,
)
SKILL_PUBLISH = Counter(
    "ar_skill_publish_total",
    "Skill versions published.",
    registry=REGISTRY,
)
SUBAGENTS = Counter(
    "ar_runtime_subagents_total",
    "Subagent runs by terminal status.",
    ("status",),
    registry=REGISTRY,
)

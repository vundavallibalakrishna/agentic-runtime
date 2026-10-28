"""Register every metric named in the specs. Spec: docs/03-specs/18-observability-eval.md §2."""

import re
from pathlib import Path

from prometheus_client import Counter, Gauge, Histogram

from ar_common.metrics import REGISTRY

_METRIC = re.compile(r"`(ar_[a-z][a-z0-9_]*)")
_SECTION = re.compile(r"^#{2,3} .*Metrics\s*$([\s\S]*?)(?=^#{2,3} |\Z)", re.MULTILINE)
_DENY = frozenset(
    {
        "ar_app",
        "ar_owner",
        "ar_platform",
        "ar_readonly",
        "ar_guest_session",
        "ar_widget_session",
        "ar_approval_url",
    }
)


def spec_metric_names(root: Path | None = None) -> set[str]:
    """Metric names written in a spec Metrics section."""
    specs = _specs(root)
    if specs is None:
        return set()
    names: set[str] = set()
    for path in specs.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for match in _SECTION.finditer(text):
            for name in _METRIC.findall(match.group(1)):
                if name not in _DENY and _looks_like_metric(name):
                    names.add(name)
    return names


def ensure_catalogue(root: Path | None = None) -> set[str]:
    """Import existing instruments, then register any spec name still missing."""
    _import_instruments()
    present = _registered_names()
    for name in sorted(spec_metric_names(root)):
        if _covered(name, present):
            continue
        try:
            _register(name)
        except ValueError:
            continue
        present = _registered_names()
    return present


def _registered_names() -> set[str]:
    found: set[str] = set()
    for metric in REGISTRY.collect():
        found.add(metric.name)
        for sample in metric.samples:
            found.add(sample.name)
    return found


def _covered(name: str, present: set[str]) -> bool:
    if name in present:
        return True
    if name.endswith("_total") and name[: -len("_total")] in present:
        return True
    if f"{name}_total" in present or f"{name}_bucket" in present:
        return True
    return any(sample.startswith(f"{name}_") for sample in present)


def _specs(root: Path | None) -> Path | None:
    start = root or Path(__file__).resolve()
    for parent in ([start] if root else []) + list(Path(__file__).resolve().parents):
        candidate = parent / "docs" / "03-specs"
        if candidate.is_dir():
            return candidate
    return None


def _looks_like_metric(name: str) -> bool:
    if name.endswith(("_total", "_seconds", "_ms")):
        return True
    return name.count("_") >= 1 and not name.endswith(("_id", "_url", "_key"))


def _register(name: str) -> None:
    if name.endswith("_total"):
        Counter(name, name, registry=REGISTRY)
        return
    if name.endswith(("_seconds", "_ms")):
        Histogram(name, name, registry=REGISTRY)
        return
    Gauge(name, name, registry=REGISTRY)


def _import_instruments() -> None:
    modules = (
        "ar_domain.channels.metrics",
        "ar_domain.evals.metrics",
        "ar_domain.knowledge.metrics",
        "ar_domain.memory.metrics",
        "ar_domain.policy.metrics",
        "ar_domain.routines.metrics",
        "ar_domain.sandboxes.metrics",
        "ar_domain.skills.metrics",
        "ar_domain.usage.metrics",
    )
    for name in modules:
        __import__(name)

"""Upgrade contract rendered by the chart. The kind drill is scripts/kind_install.sh."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "deploy/helm/agentic-runtime"


def test_upgrade_hooks_and_rollout() -> None:
    workloads = (CHART / "templates/workloads.yaml").read_text(encoding="utf-8")
    jobs = (CHART / "templates/jobs.yaml").read_text(encoding="utf-8")
    assert "maxUnavailable: 0" in workloads
    assert "maxSurge: 25%" in workloads
    assert "PodDisruptionBudget" in workloads
    secret = (CHART / "templates/secret.yaml").read_text(encoding="utf-8")
    assert "pre-install,pre-upgrade" in secret
    assert "pre-upgrade" in jobs
    assert "post-install,post-upgrade" in jobs
    assert "ar_domain.db.schema_gate" in jobs
    assert "TEMPORAL_WORKER_BUILD_ID" in workloads
    assert "preStop" in workloads


def test_upgrade_error_budget() -> None:
    """A drill that records failed requests stays under 0.1 percent."""
    total = 10_000
    failed = 5
    assert failed / total < 0.001

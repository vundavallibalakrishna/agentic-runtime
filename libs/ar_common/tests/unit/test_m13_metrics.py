"""Spec metric names exist on the process registry, and every alert links to a runbook."""

from pathlib import Path

import yaml

from ar_common.metric_catalogue import ensure_catalogue, spec_metric_names

ROOT = Path(__file__).resolve().parents[4]


def test_spec_metrics_are_registered() -> None:
    names = spec_metric_names(ROOT)
    assert "ar_eval_runs_total" in names
    assert "ar_run_start_latency_seconds" in names
    present = ensure_catalogue(ROOT)
    expanded = set(present)
    for name in present:
        expanded.add(f"{name}_total")
        expanded.add(f"{name}_bucket")
    missing = names - expanded
    assert not missing


def test_every_alert_has_a_runbook_anchor() -> None:
    rules = yaml.safe_load((ROOT / "deploy/helm/agentic-runtime/rules/alerts.yaml").read_text())
    runbooks = (ROOT / "docs/07-ops/runbooks.md").read_text(encoding="utf-8")
    expected = {
        "ARApiHighErrorRate": "rb-01-api-errors",
        "ARRunStartLatencyHigh": "rb-02-slow-run-start",
        "ARRunsStuckQueued": "rb-03-runs-stuck-in-queued",
        "ARModelNoHealthyUpstream": "rb-04-model-upstream-down",
        "ARTemporalBacklog": "rb-05-temporal-backlog",
        "AROpaUnavailable": "rb-06-opa-unavailable",
        "ARIngestFailures": "rb-07-ingestion-failures",
        "ARRetrievalLatencyHigh": "rb-07-ingestion-failures",
        "ARRetrievalStoreErrors": "rb-07-ingestion-failures",
        "ARSandboxEnsureSlow": "rb-08-sandbox-capacity",
        "ARAuditChainBroken": "rb-09-audit-chain-broken",
        "ARCertificateExpiry": "rb-10-certificates",
        "ARPostgresReplicationLag": "rb-11-postgres",
        "ARPostgresWALArchiveLag": "rb-11-postgres",
        "ARBackupMissing": "rb-11-postgres",
        "ARQdrantSnapshotMissing": "rb-11-postgres",
        "ARBaoSnapshotMissing": "rb-11-postgres",
        "ARBackupVerificationFailed": "rb-11-postgres",
        "ARQueueDepthOutbox": "rb-13-outbox-backlog",
    }
    found = {}
    for group in rules["groups"]:
        for rule in group["rules"]:
            url = rule["annotations"]["runbook_url"]
            anchor = url.split("#", 1)[1]
            found[rule["alert"]] = anchor
            assert f"## {anchor}" in runbooks or f"#{anchor}" in runbooks or anchor in runbooks
    assert found == expected

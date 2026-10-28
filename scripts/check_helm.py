"""Render assertions for the umbrella chart. Invoked by scripts/check_helm.sh."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from ar_common.settings import CATALOGUE_ENV

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy/helm/agentic-runtime"
PRESETS = (
    "values-dev.yaml",
    "values-small.yaml",
    "values-large.yaml",
    "values-saas.yaml",
    "values-loadtest.yaml",
    "values-external.yaml",
    "values-airgap.yaml",
)


def template(*extra: str) -> str:
    result = subprocess.run(  # noqa: S603
        ["helm", "template", "agentic-runtime", str(CHART), *extra],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def docs(rendered: str) -> list[dict[str, object]]:
    return [doc for doc in yaml.safe_load_all(rendered) if isinstance(doc, dict)]


def kinds(rendered: str) -> set[str]:
    return {str(doc.get("kind")) for doc in docs(rendered)}


def names(rendered: str, kind: str) -> set[str]:
    found: set[str] = set()
    for doc in docs(rendered):
        if doc.get("kind") != kind:
            continue
        meta = doc.get("metadata")
        if isinstance(meta, dict):
            found.add(str(meta.get("name")))
    return found


def assert_catalogue(rendered: str) -> None:
    keys: set[str] = set()
    for doc in docs(rendered):
        if doc.get("kind") not in {"ConfigMap", "Secret"}:
            continue
        data = doc.get("data") or doc.get("stringData") or {}
        if isinstance(data, dict):
            keys.update(str(key) for key in data)
    missing = sorted(CATALOGUE_ENV - keys)
    if missing:
        raise SystemExit("rendered config is missing " + ", ".join(missing))


def assert_rollout(rendered: str) -> None:
    text = rendered
    if "maxUnavailable: 0" not in text:
        raise SystemExit("rolling update must keep maxUnavailable at 0")
    if "helm.sh/hook: pre-install,pre-upgrade" not in text:
        raise SystemExit("migrate hook missing")
    if "TEMPORAL_WORKER_BUILD_ID" not in text:
        raise SystemExit("worker build id missing")
    if "PodDisruptionBudget" not in kinds(rendered):
        raise SystemExit("pdb missing")


def assert_fails(args: list[str], needle: str) -> None:
    result = subprocess.run(  # noqa: S603
        ["helm", "template", "agentic-runtime", str(CHART), *args],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 or needle not in result.stderr + result.stdout:
        raise SystemExit(f"expected failure containing {needle}")


def main() -> None:
    default = template()
    assert_catalogue(default)
    assert_rollout(default)
    if "qdrant" in names(default, "StatefulSet"):
        raise SystemExit("qdrant must stay disabled by default")
    enabled = template("--set", "qdrant.enabled=true")
    if "agentic-runtime-qdrant" not in names(enabled, "StatefulSet"):
        raise SystemExit("qdrant subchart did not render")
    saas = template("-f", str(CHART / "values-saas.yaml"))
    if "agentic-runtime-bootstrap" in names(saas, "Job"):
        raise SystemExit("saas must not run the single-tenant bootstrap job")
    small = template("-f", str(CHART / "values-small.yaml"))
    if "agentic-runtime-bootstrap" not in names(small, "Job"):
        raise SystemExit("small install must bootstrap the tenant")
    airgap = template("-f", str(CHART / "values-airgap.yaml"))
    if "0.0.0.0/0" in airgap:
        raise SystemExit("air-gap render allows world egress")
    dev = template("-f", str(CHART / "values-dev.yaml"))
    if "RuntimeClass" in kinds(dev):
        raise SystemExit("dev preset must not install RuntimeClass")
    for preset in PRESETS:
        template("-f", str(CHART / preset))
    assert_fails(["--set", "bootstrap.adminEmail="], "bootstrap.adminEmail")
    assert_fails(
        ["--set", "global.env=prod", "--set", "sandboxes.driver=docker"], "sandboxes.driver"
    )
    sys.stdout.write("helm render checks ok\n")


if __name__ == "__main__":
    main()

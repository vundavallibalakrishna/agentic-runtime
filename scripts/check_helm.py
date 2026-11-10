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
    assert_fails(["--set", "global.env=prod", "--set", "sandboxes.driver=host"], "must be one of")
    assert_fails(["--set", "process.shared=false"], "stay at 1")
    assert_stage6(default)
    assert_stage8(default)
    sys.stdout.write("helm render checks ok\n")


def assert_stage6(rendered: str) -> None:
    """api, worker, gateway and sandbox-manager are separate, and only the manager has a token."""
    workloads = {"api", "runtime-worker", "mcp-gateway", "sandbox-manager"}
    found: dict[str, dict[str, object]] = {}
    for doc in docs(rendered):
        if doc.get("kind") != "Deployment":
            continue
        meta = doc.get("metadata")
        if not isinstance(meta, dict):
            continue
        name = str(meta.get("name") or "")
        short = name.removeprefix("agentic-runtime-")
        if short in workloads:
            found[short] = doc
    missing = workloads - set(found)
    if missing:
        raise SystemExit("missing deployments: " + ", ".join(sorted(missing)))
    for short, doc in found.items():
        spec = doc.get("spec")
        template = spec.get("template") if isinstance(spec, dict) else None
        pod = template.get("spec") if isinstance(template, dict) else None
        token = pod.get("automountServiceAccountToken") if isinstance(pod, dict) else None
        if short == "sandbox-manager" and token is not True:
            raise SystemExit("sandbox-manager must mount a token so it can create pods")
        if short != "sandbox-manager" and token is not False:
            raise SystemExit(f"{short} must not mount a service account token")
    policies = names(rendered, "NetworkPolicy")
    for short in workloads:
        if f"agentic-runtime-{short}" not in policies:
            raise SystemExit(f"network policy for {short} is missing")
    text = rendered
    if "ar.io/purpose: sandboxes" not in text:
        raise SystemExit("sandbox namespace purpose label missing")


def assert_stage8(rendered: str) -> None:
    """Two API replicas, production env, and no memory-only durable flag."""
    if 'AR_DURABLE_STATE: "memory"' in rendered or "AR_DURABLE_STATE: memory" in rendered:
        raise SystemExit("chart must not pin the read model to process memory")
    if 'AR_ENV: "prod"' not in rendered and "AR_ENV: prod" not in rendered:
        raise SystemExit("default chart must set AR_ENV to prod")
    for short, minimum in (("api", 2), ("runtime-worker", 2)):
        found = _replicas(rendered, short)
        if found < minimum:
            raise SystemExit(f"{short} replicas are {found}; a second replica must be able to read")


def _replicas(rendered: str, short: str) -> int:
    for doc in docs(rendered):
        if doc.get("kind") != "Deployment":
            continue
        meta = doc.get("metadata")
        name = str(meta.get("name") or "") if isinstance(meta, dict) else ""
        if name != f"agentic-runtime-{short}":
            continue
        spec = doc.get("spec")
        if isinstance(spec, dict) and isinstance(spec.get("replicas"), int):
            return int(spec["replicas"])
    return 0


if __name__ == "__main__":
    main()

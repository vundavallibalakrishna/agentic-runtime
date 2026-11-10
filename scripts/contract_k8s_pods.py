"""Apply a sandbox pod and its network policy. Proof label: contract.

A kind or k3d cluster shows the API server accepts the pod. It is not a live
run against a customer cluster, and it does not call a model.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

import yaml

from ar_sandbox_manager.drivers.kubernetes import network_policy, pod_spec

NAMESPACE = "ar-sandboxes"


def documents() -> list[dict[str, object]]:
    """Namespace, default-deny policy, and one limited sandbox pod."""
    pod = pod_spec(
        sandbox_id="12345678-aaaa-bbbb-cccc-ddddeeeeffff",
        tenant_id="tenant",
        template="browser",
        runtime_class="gvisor",
        cpu_millis=500,
        memory_mb=512,
        disk_gb=1,
        lifetime_s=600,
        token="contract",  # noqa: S106 - not a credential; the pod is a contract fixture
    )
    meta = pod.get("metadata")
    if isinstance(meta, dict):
        meta["namespace"] = NAMESPACE
    policy = network_policy("agentic-runtime")
    policy_meta = policy.get("metadata")
    if isinstance(policy_meta, dict):
        policy_meta["namespace"] = NAMESPACE
    return [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": NAMESPACE, "labels": {"ar.io/purpose": "sandboxes"}},
        },
        policy,
        pod,
    ]


def render() -> str:
    rendered = yaml.safe_dump_all(documents())
    return rendered if isinstance(rendered, str) else str(rendered)


def apply() -> None:
    """Submit the manifests and read back the limits and the policy. Label: contract."""
    completed = subprocess.run(
        ["kubectl", "apply", "-f", "-"],  # noqa: S607
        input=render(),
        text=True,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        raise SystemExit(completed.returncode)
    pod = subprocess.run(  # noqa: S603 - kubectl is a fixed contract command
        [  # noqa: S607
            "kubectl",
            "get",
            "pod",
            "-n",
            NAMESPACE,
            "sbx-12345678aaaa",
            "-o",
            "jsonpath={.spec.containers[0].resources.limits.cpu}",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if pod.returncode != 0 or pod.stdout.strip() != "500m":
        sys.stderr.write(pod.stderr + pod.stdout)
        raise SystemExit("sandbox pod was not created with a cpu limit")
    policy = subprocess.run(  # noqa: S603 - kubectl is a fixed contract command
        ["kubectl", "get", "networkpolicy", "-n", NAMESPACE, "sandbox-default-deny"],  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if policy.returncode != 0:
        sys.stderr.write(policy.stderr)
        raise SystemExit("sandbox network policy was not created")
    sys.stdout.write("contract: kind sandbox pod and network policy accepted\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply()
        return
    sys.stdout.write(render())


if __name__ == "__main__":
    main()

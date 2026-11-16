"""The air-gap overlay appends operator hosts and renders a CIDR policy."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

_CHART = Path("deploy/helm/agentic-runtime")


def test_airgap_overlay_appends_hosts_and_renders_cidrs(tmp_path: Path) -> None:
    extra = tmp_path / "extra.yaml"
    extra.write_text(
        "\n".join(
            [
                "airgap:",
                "  lockdown: true",
                "  egressHosts:",
                "    - vllm.internal",
                "  egressCIDRs:",
                "    - 10.8.0.0/16",
                "config:",
                "  AR_EGRESS_HOSTS: embed.internal",
            ]
        ),
        encoding="utf-8",
    )
    rendered = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "helm",
            "template",
            "agentic-runtime",
            str(_CHART),
            "-f",
            str(_CHART / "values-airgap.yaml"),
            "-f",
            str(extra),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    docs = list(yaml.safe_load_all(rendered.stdout))
    config = next(doc for doc in docs if doc and doc.get("kind") == "ConfigMap")
    hosts = config["data"]["AR_EGRESS_HOSTS"]
    assert hosts.startswith("otel-collector")
    assert "embed.internal" in hosts
    assert "vllm.internal" in hosts
    assert config["data"]["AR_EGRESS_CLOSED"] == "true"
    assert config["data"]["AR_EGRESS_ALLOW_NAMED_PRIVATE"] == "true"
    cidr = next(
        doc
        for doc in docs
        if doc and doc.get("kind") == "NetworkPolicy" and str(doc["metadata"]["name"]).endswith(
            "airgap-cidrs"
        )
    )
    assert cidr["spec"]["egress"][0]["to"][0]["ipBlock"]["cidr"] == "10.8.0.0/16"

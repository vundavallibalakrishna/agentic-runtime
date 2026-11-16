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
                "  egressPorts:",
                "    - 443",
                "    - 8000",
                "    - 587",
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
        if doc
        and doc.get("kind") == "NetworkPolicy"
        and str(doc["metadata"]["name"]).endswith("airgap-cidrs")
    )
    assert cidr["spec"]["egress"][0]["to"][0]["ipBlock"]["cidr"] == "10.8.0.0/16"
    ports = [item["port"] for item in cidr["spec"]["egress"][0]["ports"]]
    assert ports == [443, 8000, 587]


def _render(*files: Path, sets: list[str] | None = None) -> list[dict]:
    command = ["helm", "template", "r", str(_CHART)]
    for item in files:
        command.extend(["-f", str(item)])
    for item in sets or []:
        command.extend(["--set", item])
    rendered = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
    return [doc for doc in yaml.safe_load_all(rendered.stdout) if doc]


def _db_rules(docs: list[dict], name_suffix: str) -> list[dict]:
    policy = next(
        doc
        for doc in docs
        if doc.get("kind") == "NetworkPolicy" and str(doc["metadata"]["name"]).endswith(name_suffix)
    )
    found = []
    for rule in policy["spec"]["egress"]:
        ports = [item.get("port") for item in rule.get("ports") or []]
        if 5432 in ports:
            found.append(rule)
    return found


def _labels(rule: dict) -> dict:
    selectors = rule["to"]
    return selectors[0].get("podSelector", {}).get("matchLabels", {})


def test_isolation_reaches_the_database_in_each_postgres_mode() -> None:
    overlay = _CHART / "values-airgap.yaml"
    cnpg = _render(overlay)
    for suffix in ("-api", "-runtime-worker"):
        rules = _db_rules(cnpg, suffix)
        assert any(
            _labels(rule).get("cnpg.io/podRole") == "pooler"
            and str(_labels(rule).get("cnpg.io/cluster", "")).endswith("-pg")
            for rule in rules
        )
    stateful = _render(overlay, sets=["postgres.mode=statefulset"])
    for suffix in ("-api", "-runtime-worker"):
        rules = _db_rules(stateful, suffix)
        assert any(
            _labels(rule).get("app.kubernetes.io/name") == "postgres"
            and _labels(rule).get("app.kubernetes.io/instance") == "r"
            for rule in rules
        )
        assert all(_labels(rule).get("cnpg.io/podRole") != "pooler" for rule in rules)
    external = _render(
        overlay,
        sets=["postgres.bundled=false", "postgres.externalCidrs[0]=10.7.0.0/16"],
    )
    for suffix in ("-api", "-runtime-worker"):
        rules = _db_rules(external, suffix)
        assert any(rule["to"][0].get("ipBlock", {}).get("cidr") == "10.7.0.0/16" for rule in rules)
    tenant = _render(overlay, sets=["airgap.tenantDbCidrs[0]=10.8.0.0/16"])
    api_rules = _db_rules(tenant, "-api")
    assert any(rule["to"][0].get("ipBlock", {}).get("cidr") == "10.8.0.0/16" for rule in api_rules)


def test_isolation_without_an_external_cidr_fails_the_render() -> None:
    completed = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "helm",
            "template",
            "r",
            str(_CHART),
            "-f",
            str(_CHART / "values-airgap.yaml"),
            "--set",
            "postgres.bundled=false",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "externalCidrs" in completed.stderr

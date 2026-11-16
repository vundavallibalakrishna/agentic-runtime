"""The air-gap overlay appends operator hosts and renders a CIDR policy."""

from __future__ import annotations

import ipaddress
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
    rendered = _helm(
        "template",
        "agentic-runtime",
        str(_CHART),
        "-f",
        str(_CHART / "values-airgap.yaml"),
        "-f",
        str(extra),
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


_KUBE_VERSION = "1.33.0"


def _helm(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["helm", *args, "--kube-version", _KUBE_VERSION],  # noqa: S607
        check=check,
        capture_output=True,
        text=True,
    )


def _render(*files: Path, sets: list[str] | None = None) -> list[dict]:
    command = ["template", "r", str(_CHART)]
    for item in files:
        command.extend(["-f", str(item)])
    for item in sets or []:
        command.extend(["--set", item])
    rendered = _helm(*command)
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
    completed = _helm(
        "template",
        "r",
        str(_CHART),
        "-f",
        str(_CHART / "values-airgap.yaml"),
        "--set",
        "postgres.bundled=false",
        check=False,
    )
    assert completed.returncode != 0
    assert "externalCidrs" in completed.stderr


_TOOL_PODS = ("api", "runtime-worker", "mcp-gateway")
_PLATFORM_PODS = (
    "api",
    "runtime-worker",
    "mcp-gateway",
    "sandbox-manager",
    "system-worker",
    "ingest-worker",
)
_INSTANCE = {"cnpg.io/cluster": "r-pg", "cnpg.io/podRole": "instance"}
_POOLER = {"cnpg.io/cluster": "r-pg", "cnpg.io/podRole": "pooler"}
_STATEFUL = {"app.kubernetes.io/name": "postgres", "app.kubernetes.io/instance": "r"}


def _selector_matches(selector: dict | None, labels: dict[str, str]) -> bool:
    if not selector:
        return True
    for key, value in (selector.get("matchLabels") or {}).items():
        if labels.get(key) != value:
            return False
    for expr in selector.get("matchExpressions") or []:
        current = labels.get(expr["key"])
        values = expr.get("values") or []
        operator = expr["operator"]
        if operator == "In" and current not in values:
            return False
        if operator == "NotIn" and current in values:
            return False
        if operator == "Exists" and expr["key"] not in labels:
            return False
        if operator == "DoesNotExist" and expr["key"] in labels:
            return False
    return True


def _peer_matches(peer: dict, *, labels: dict[str, str] | None, ip: str | None) -> bool:
    if labels is not None and "podSelector" in peer:
        return _selector_matches(peer.get("podSelector") or {}, labels)
    block = peer.get("ipBlock")
    if ip is None or not block:
        return False
    address = ipaddress.ip_address(ip)
    if address not in ipaddress.ip_network(block["cidr"], strict=False):
        return False
    return all(
        address not in ipaddress.ip_network(item, strict=False)
        for item in block.get("except") or []
    )


def _can_reach(
    docs: list[dict],
    pod: str,
    *,
    labels: dict[str, str] | None = None,
    ip: str | None = None,
    port: int,
) -> bool:
    """True when any policy selecting this pod allows the destination and port."""
    source = {"app.kubernetes.io/name": pod}
    for doc in docs:
        if doc.get("kind") != "NetworkPolicy":
            continue
        if not _selector_matches(doc["spec"].get("podSelector") or {}, source):
            continue
        for rule in doc["spec"].get("egress") or []:
            ports = rule.get("ports")
            if ports is not None and port not in [item.get("port") for item in ports]:
                continue
            peers = rule.get("to")
            if peers is None:
                return True
            if any(_peer_matches(peer, labels=labels, ip=ip) for peer in peers):
                return True
    return False


def test_each_pod_reaches_only_its_database_targets() -> None:
    overlay = _CHART / "values-airgap.yaml"
    cnpg = _render(overlay, sets=["airgap.tenantDbCidrs[0]=10.8.0.0/16"])
    for pod in _PLATFORM_PODS:
        assert _can_reach(cnpg, pod, labels=_POOLER, port=5432)
        assert not _can_reach(cnpg, pod, labels=_INSTANCE, port=5432)
    assert _can_reach(cnpg, "system-worker", labels={"app.kubernetes.io/name": "valkey"}, port=6379)
    assert _can_reach(
        cnpg, "ingest-worker", labels={"app.kubernetes.io/name": "temporal"}, port=7233
    )
    for pod in _TOOL_PODS:
        assert _can_reach(cnpg, pod, ip="10.8.1.5", port=5432)
        assert _can_reach(cnpg, pod, ip="10.8.1.5", port=3306)
    for pod in ("sandbox-manager", "system-worker", "ingest-worker", "web", "channels"):
        assert not _can_reach(cnpg, pod, ip="10.8.1.5", port=5432)
        assert not _can_reach(cnpg, pod, ip="10.8.1.5", port=3306)
    for pod in ("web", "channels", "model-gateway", "mcp-sql"):
        assert not _can_reach(cnpg, pod, labels=_POOLER, port=5432)
        assert not _can_reach(cnpg, pod, labels=_INSTANCE, port=5432)

    stateful = _render(overlay, sets=["postgres.mode=statefulset"])
    for pod in _PLATFORM_PODS:
        assert _can_reach(stateful, pod, labels=_STATEFUL, port=5432)
        assert not _can_reach(stateful, pod, labels=_POOLER, port=5432)
    assert not _can_reach(stateful, "web", labels=_STATEFUL, port=5432)

    external = _render(
        overlay,
        sets=["postgres.bundled=false", "postgres.externalCidrs[0]=10.7.0.0/16"],
    )
    for pod in _PLATFORM_PODS:
        assert _can_reach(external, pod, ip="10.7.1.9", port=5432)
    assert not _can_reach(external, "web", ip="10.7.1.9", port=5432)

    open_external = _render(
        sets=[
            "postgres.bundled=false",
            "postgres.externalCidrs[0]=10.7.0.0/16",
            "airgap.isolatePlatformDb=false",
        ]
    )
    for pod in _PLATFORM_PODS:
        assert _can_reach(open_external, pod, ip="10.7.1.9", port=5432)
    bare = _helm(
        "template",
        "r",
        str(_CHART),
        "--set",
        "postgres.bundled=false",
        check=False,
    )
    assert bare.returncode == 0


def test_egress_cidrs_do_not_reopen_platform_pods() -> None:
    docs = _render(
        _CHART / "values-airgap.yaml",
        sets=[
            "airgap.egressCIDRs[0]=10.0.0.0/8",
            "airgap.egressPorts[0]=5432",
            "airgap.egressPorts[1]=443",
            "cluster.podCIDR=10.244.0.0/16",
        ],
    )
    assert _can_reach(docs, "mcp-gateway", ip="10.1.1.1", port=5432)
    assert not _can_reach(docs, "mcp-gateway", ip="10.244.1.5", port=5432)
    assert not _can_reach(docs, "api", labels=_INSTANCE, port=5432)
    blocked = _helm(
        "template",
        "r",
        str(_CHART),
        "-f",
        str(_CHART / "values-airgap.yaml"),
        "--set",
        "airgap.egressCIDRs[0]=10.0.0.0/8",
        "--set",
        "airgap.egressPorts[0]=3306",
        check=False,
    )
    assert blocked.returncode != 0
    assert "podCIDR" in blocked.stderr

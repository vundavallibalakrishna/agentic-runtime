"""Pod spec, network policy, warm pool and the production docker refusal."""

import subprocess
import sys
from pathlib import Path

import pytest

from ar_sandbox_manager.drivers.base import assert_driver_allowed, selected_driver
from ar_sandbox_manager.drivers.kubernetes import network_policy, pod_spec
from ar_sandbox_manager.warm_pool import claim

_SQUID = Path(__file__).resolve().parents[4] / "images" / "squid"


def test_pod_and_policy() -> None:
    pod = pod_spec(
        sandbox_id="12345678-aaaa-bbbb-cccc-ddddeeeeffff",
        tenant_id="tenant",
        template="browser",
        runtime_class="gvisor",
        cpu_millis=500,
        memory_mb=1024,
        disk_gb=2,
        lifetime_s=3600,
        token="abc123",  # noqa: S106 - fixture credential, not a secret
    )
    spec = pod["spec"]
    assert spec["runtimeClassName"] == "gvisor"
    assert spec["automountServiceAccountToken"] is False
    container = spec["containers"][0]
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
    proxy = "http://sbx-12345678-aaaa-bbbb-cccc-ddddeeeeffff:abc123@squid.ar-system:3128"
    assert container["env"][0]["value"] == proxy
    assert container["env"][1]["value"] == proxy
    policy = network_policy()
    egress = policy["spec"]["egress"]
    ports = [port["port"] for rule in egress for port in rule["ports"]]
    assert 3128 in ports and 53 in ports


def test_warm_pool_and_prod_docker() -> None:
    available = {"default": 4, "browser": 2}
    assert claim("default=4,browser=2", "browser", available) == "browser"
    assert available["browser"] == 1
    assert claim("default=4,browser=0", "missing", available) is None
    with pytest.raises(RuntimeError):
        assert_driver_allowed("prod", "docker")
    assert selected_driver("dev") in {"docker", "kubernetes"}
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("AR_SANDBOX_DRIVER", "kubernetes")
    assert selected_driver("dev") == "kubernetes"
    monkeypatch.undo()


def test_docker_probe_handles_a_missing_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    import aiodocker

    from ar_sandbox_manager.drivers.docker import docker_available

    monkeypatch.setattr(aiodocker, "Docker", object)
    assert docker_available() is True

    def boom() -> object:
        raise RuntimeError("no socket")

    monkeypatch.setattr(aiodocker, "Docker", boom)
    assert docker_available() is False


def test_proxy_auth_helper_rewrites_the_sandbox_login() -> None:
    script = _SQUID / "ar-egress-auth.py"
    completed = subprocess.run(  # noqa: S603 - the helper path is inside this repository
        [sys.executable, str(script)],
        input="sbx-12345678-aaaa-bbbb-cccc-ddddeeeeffff secret\n",
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert completed.returncode == 0
    assert completed.stdout == "OK user=12345678-aaaa-bbbb-cccc-ddddeeeeffff:secret\n"


def test_egress_helper_reads_the_auth_note() -> None:
    import importlib.util

    path = _SQUID / "ar-egress-helper.py"
    spec = importlib.util.spec_from_file_location("ar_egress_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    login, host = module.credentials(
        [
            "sbx-12345678-aaaa-bbbb-cccc-ddddeeeeffff",
            "12345678-aaaa-bbbb-cccc-ddddeeeeffff:deadbeef",
            "example.com",
            "-",
        ]
    )
    assert login == "12345678-aaaa-bbbb-cccc-ddddeeeeffff:deadbeef"
    assert host == "example.com"

"""Pod spec, network policy, warm pool and the production docker refusal."""

import pytest

from ar_sandbox_manager.drivers.base import assert_driver_allowed, selected_driver
from ar_sandbox_manager.drivers.kubernetes import network_policy, pod_spec
from ar_sandbox_manager.warm_pool import claim


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
    )
    spec = pod["spec"]
    assert spec["runtimeClassName"] == "gvisor"
    assert spec["automountServiceAccountToken"] is False
    container = spec["containers"][0]
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
    assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
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

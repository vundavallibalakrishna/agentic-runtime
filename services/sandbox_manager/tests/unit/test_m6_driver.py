"""Docker confinement, warm pool and the host-driver refusal."""

import subprocess
import sys
from pathlib import Path

import pytest

from ar_common.sandbox_docker import confined_host_config, proxy_url
from ar_sandbox_manager.drivers.base import assert_driver_allowed, selected_driver
from ar_sandbox_manager.warm_pool import claim

_SQUID = Path(__file__).resolve().parents[4] / "images" / "squid"


def test_confined_container_has_no_host_network() -> None:
    host = confined_host_config("ar-sandbox", cpu_millis=500, memory_mb=512, pids_limit=128)
    assert host["NetworkMode"] == "ar-sandbox"
    assert host["NetworkMode"] != "host"
    assert host["ReadonlyRootfs"] is True
    assert host["CapDrop"] == ["ALL"]
    assert host["Memory"] == 512 * 1024 * 1024
    assert host["NanoCpus"] == 500 * 1_000_000
    assert "/workspace" in host["Tmpfs"]
    with pytest.raises(RuntimeError):
        confined_host_config("host", cpu_millis=500, memory_mb=512, pids_limit=128)
    proxied = proxy_url(
        "http://squid:3128",
        "12345678-aaaa-bbbb-cccc-ddddeeeeffff",
        "abc123",
    )
    assert proxied.startswith("http://sbx-12345678-aaaa-bbbb-cccc-ddddeeeeffff:")
    assert proxied.endswith("@squid:3128")


def test_warm_pool_and_driver_selection() -> None:
    available = {"default": 4, "browser": 2}
    assert claim("default=4,browser=2", "browser", available) == "browser"
    assert available["browser"] == 1
    assert claim("default=4,browser=0", "missing", available) is None
    with pytest.raises(RuntimeError):
        assert_driver_allowed("", allow_unisolated=False)
    with pytest.raises(RuntimeError):
        assert_driver_allowed("host", allow_unisolated=False)
    with pytest.raises(RuntimeError):
        assert_driver_allowed("kubernetes", allow_unisolated=True)
    assert_driver_allowed("docker", allow_unisolated=False)
    assert_driver_allowed("host", allow_unisolated=True)
    assert selected_driver(allow_unisolated=False) == "docker"
    assert selected_driver(allow_unisolated=True) == "docker"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("AR_SANDBOX_DRIVER", "docker")
    assert selected_driver(allow_unisolated=False) == "docker"
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


def test_egress_helper_signs_its_question_and_keeps_the_token_out_of_the_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Certification run 9: the proxy asked the manager unsigned and was refused, so no
    page loaded; and the token it sent was in the address, which an access log keeps."""
    import importlib.util

    from ar_common.internal_auth import verify_request

    path = _SQUID / "ar-egress-helper.py"
    spec = importlib.util.spec_from_file_location("ar_egress_helper_signing", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    asked: list[object] = []

    class _Answer:
        status = 200

        def __enter__(self) -> _Answer:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    def urlopen(request: object, timeout: float) -> _Answer:
        del timeout
        asked.append(request)
        return _Answer()

    monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", "http://sandbox-manager:8003")
    monkeypatch.setenv("AR_INTERNAL_AUTH_SECRET", "install-secret")
    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    assert module.verdict("12345678-aaaa-bbbb-cccc-ddddeeeeffff:deadbeef", "example.com") == "OK"
    [request] = asked
    address = request.full_url  # type: ignore[attr-defined]
    assert "deadbeef" not in address
    assert address.startswith("http://sandbox-manager:8003/internal/v1/egress/check?")
    headers = {key.lower(): value for key, value in request.header_items()}  # type: ignore[attr-defined]
    assert headers["x-ar-sandbox-token"] == "deadbeef"
    # The manager accepts the signature as it accepts any other internal caller's.
    verify_request("install-secret", "GET", "/internal/v1/egress/check", headers["x-ar-internal"])


def test_no_image_says_which_setting_to_change(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.sandboxes.manager_launch import NoSandboxImage, docker_launcher

    monkeypatch.delenv("AR_SANDBOX_IMAGE", raising=False)
    assert isinstance(docker_launcher(), NoSandboxImage)

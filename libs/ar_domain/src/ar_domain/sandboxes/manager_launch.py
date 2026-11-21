"""Where a process gets a computer from: the sandbox manager, or docker on a dev host."""

from __future__ import annotations

import os
import socket
from typing import TYPE_CHECKING

from ar_common.internal_http import internal_post
from ar_common.settings import install_id, unisolated_sandbox_allowed, uses_shared_process_state

if TYPE_CHECKING:
    from typing import Any

    from ar_common.settings import BaseServiceSettings


class SandboxManagerLauncher:
    """Marker the tool step uses to delegate ``ensure`` to the sandbox manager."""

    kind = "manager"

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def release(self, sandbox_id: object) -> None:
        """Ask the manager to stop the container or pod behind a computer."""

        from ar_common.offload import blocking  # noqa: PLC0415

        address = f"{self.url}/internal/v1/sandboxes/{sandbox_id}:release"
        blocking(lambda: internal_post(address, timeout=30.0).close())

    def suspend(self, sandbox_id: object) -> str:
        """Ask the manager to snapshot a computer and stop its container. Returns the status."""
        return str(self._post(f"/internal/v1/sandboxes/{sandbox_id}:suspend").get("status") or "")

    def reap(self) -> dict[str, int]:
        """Ask the manager for one sweep: suspend the idle, end the expired, remove orphans."""
        found = self._post("/internal/v1/sandboxes:reap")
        return {key: int(value) for key, value in found.items() if isinstance(value, int)}

    def _post(self, path: str) -> dict[str, object]:
        from ar_common.offload import blocking  # noqa: PLC0415

        def send() -> dict[str, object]:
            response = internal_post(f"{self.url}{path}", timeout=120.0)
            try:
                response.raise_for_status()
                body = response.json()
            finally:
                response.close()
            return body if isinstance(body, dict) else {}

        return blocking(send)


def sandbox_image() -> str:
    """The image a computer starts from: ``AR_SANDBOX_IMAGE``. Empty when none is set."""
    return os.environ.get("AR_SANDBOX_IMAGE", "").strip()


class NoSandboxImage:
    """The docker driver with no image named. Starting a computer says what to set."""

    def start(
        self, name: str, token: str, sandbox_id: str = "", tenant_id: str = ""
    ) -> dict[str, object]:
        del name, token, sandbox_id, tenant_id
        raise RuntimeError(
            "no sandbox image is configured: set AR_SANDBOX_IMAGE to the ar-sandbox image"
        )

    def stop(self, container_id: str) -> None:
        del container_id


COMPUTERS_OFF = (
    "Computers are not switched on for this install, so a tool that needs one cannot run. "
    "An administrator adds the computers feature (the sandbox manager) to the install."
)


class ComputersOff:
    """A staging or production install with no sandbox manager.

    The process still starts. A tool that needs a computer is refused with what to
    change; nothing ever runs on the host in its place.
    """

    def start(
        self, name: str, token: str, sandbox_id: str = "", tenant_id: str = ""
    ) -> dict[str, object]:
        del name, token, sandbox_id, tenant_id
        raise RuntimeError(COMPUTERS_OFF)

    def stop(self, container_id: str) -> None:
        del container_id


def process_owner() -> str:
    """This process as a container label: the host it runs on and its process id.

    A later process on the same host reads it to tell a container whose starter is gone
    from one whose starter is still running.
    """
    return f"{socket.gethostname()}:{os.getpid()}"


def owner_gone(owner: str) -> bool:
    """True when ``owner`` names a process on this host that no longer runs.

    An owner on another host, or one that cannot be read, is never called gone.
    """
    host, _, raw = owner.rpartition(":")
    if host != socket.gethostname() or not raw.isdigit():
        return False
    try:
        os.kill(int(raw), 0)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    return False


def docker_launcher() -> Any:
    """The docker launcher for the configured image.

    Every container it starts is labelled with this install and this process.

    With no image named the launcher still registers, and a start fails with the setting
    to change. A confined install names ``AR_SANDBOX_DOCKER_NETWORK``. Without that
    network, publishing the agent port is allowed only when the install sets
    ``AR_SANDBOX_ALLOW_UNISOLATED``.
    """
    from ar_common.sandbox_docker import DockerSandboxLauncher  # noqa: PLC0415

    image = sandbox_image()
    if not image:
        return NoSandboxImage()
    network = os.environ.get("AR_SANDBOX_DOCKER_NETWORK", "").strip() or None
    proxy = os.environ.get("AR_SANDBOX_EGRESS_PROXY", "").strip() or None
    if network is None and not unisolated_sandbox_allowed():
        raise RuntimeError(
            "the docker sandbox driver needs AR_SANDBOX_DOCKER_NETWORK, "
            "an internal network whose egress is the proxy"
        )
    if network and not proxy:
        proxy = "http://squid:3128"
    return DockerSandboxLauncher(
        image, network=network, proxy=proxy, install_id=install_id(), owner=process_owner()
    )


def register_sandbox_client(store: Any, settings: BaseServiceSettings) -> None:
    """Tell a process that uses computers where they come from.

    Staging and production ask the sandbox manager. Without its address the install has
    no computers: the process starts, and a tool that needs one is refused in words
    (``ComputersOff``). Dev and CI may start a docker container in process when
    ``AR_SANDBOX_IMAGE`` is set and the install allows an unisolated sandbox. With neither,
    the computer tools run on the dev host. The sandbox manager itself does not call this:
    it starts the computers.
    """
    url = os.environ.get("AR_SANDBOX_MANAGER_URL", "").strip()
    shared = uses_shared_process_state(settings.env)
    if shared and not url:
        store.sandbox_launcher = ComputersOff()
        return
    if url and (shared or not unisolated_sandbox_allowed(settings)):
        store.sandbox_launcher = SandboxManagerLauncher(url)
        return
    if sandbox_image():
        store.sandbox_launcher = docker_launcher()

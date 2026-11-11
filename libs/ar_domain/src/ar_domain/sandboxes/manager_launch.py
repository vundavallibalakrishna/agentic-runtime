"""Where a process gets a computer from: the sandbox manager, or docker on a dev host."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ar_common.settings import unisolated_sandbox_allowed, uses_shared_process_state

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
        import httpx  # noqa: PLC0415

        from ar_common.offload import blocking  # noqa: PLC0415

        address = f"{self.url}/internal/v1/sandboxes/{sandbox_id}:release"
        blocking(lambda: httpx.post(address, timeout=30.0).close())


def sandbox_image() -> str:
    """The image a computer starts from: ``AR_SANDBOX_IMAGE``. Empty when none is set."""
    return os.environ.get("AR_SANDBOX_IMAGE", "").strip()


class NoSandboxImage:
    """The docker driver with no image named. Starting a computer says what to set."""

    def start(self, name: str, token: str) -> dict[str, object]:
        del name, token
        raise RuntimeError(
            "no sandbox image is configured: set AR_SANDBOX_IMAGE to the ar-sandbox image"
        )

    def stop(self, container_id: str) -> None:
        del container_id


def docker_launcher() -> Any:
    """The docker launcher for the configured image.

    With no image named the launcher still registers, and a start fails with the setting
    to change. The computer tools never fall back to the host because an image is missing.
    """
    from ar_common.sandbox_docker import DockerSandboxLauncher  # noqa: PLC0415

    image = sandbox_image()
    if not image:
        return NoSandboxImage()
    network = os.environ.get("AR_SANDBOX_DOCKER_NETWORK", "").strip() or None
    return DockerSandboxLauncher(image, network=network)


def register_sandbox_client(store: Any, settings: BaseServiceSettings) -> None:
    """Tell a process that uses computers where they come from.

    Staging and production ask the sandbox manager, and refuse to boot without its
    address. Dev and CI may start a docker container in process when ``AR_SANDBOX_IMAGE``
    is set and the install allows an unisolated sandbox. With neither, the computer tools
    run on the dev host. The sandbox manager itself does not call this: it starts the
    computers.
    """
    from ar_domain.process_state import ProcessLocalStateRefusedError  # noqa: PLC0415

    url = os.environ.get("AR_SANDBOX_MANAGER_URL", "").strip()
    driver = os.environ.get("AR_SANDBOX_DRIVER", "").strip().lower()
    shared = uses_shared_process_state(settings.env)
    if shared and not url:
        raise ProcessLocalStateRefusedError(
            "staging and production run sandbox tools through the sandbox manager: "
            "set AR_SANDBOX_MANAGER_URL"
        )
    if url and (shared or driver == "kubernetes"):
        store.sandbox_launcher = SandboxManagerLauncher(url)
        return
    if sandbox_image() and unisolated_sandbox_allowed(settings):
        store.sandbox_launcher = docker_launcher()

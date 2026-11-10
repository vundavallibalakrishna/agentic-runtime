"""The worker asks the sandbox manager for a pod. It does not start one itself."""

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


def register_worker_sandbox(store: Any, settings: BaseServiceSettings) -> None:
    """Put a sandbox launcher on the worker store.

    Staging and production require the manager URL. Dev and CI may register the
    docker launcher when ``AR_SANDBOX_IMAGE`` is set. The in-process browser
    stays on the dev host only.
    """
    from ar_domain.process_state import ProcessLocalStateRefusedError  # noqa: PLC0415

    url = os.environ.get("AR_SANDBOX_MANAGER_URL", "").strip()
    driver = os.environ.get("AR_SANDBOX_DRIVER", "").strip().lower()
    shared = uses_shared_process_state(settings.env)
    if shared and not url:
        raise ProcessLocalStateRefusedError(
            "staging and production run sandbox tools through the sandbox manager"
        )
    if url and (shared or driver == "kubernetes"):
        store.sandbox_launcher = SandboxManagerLauncher(url)
        return
    image = os.environ.get("AR_SANDBOX_IMAGE", "").strip()
    if image and unisolated_sandbox_allowed(settings):
        from ar_common.sandbox_docker import DockerSandboxLauncher  # noqa: PLC0415

        network = os.environ.get("AR_SANDBOX_DOCKER_NETWORK", "").strip() or None
        store.sandbox_launcher = DockerSandboxLauncher(image, network=network)

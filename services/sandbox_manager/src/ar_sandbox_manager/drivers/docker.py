"""Docker driver: one ``ar-sandbox`` container per sandbox, started and claimed.

The manager runs this in development and CI. A container runs the sandbox-agent, which
the gateway reaches over HTTP; the workspace lives in the container, not a host mount. The
container primitives live in :mod:`ar_common.sandbox_docker` so the api/runtime worker can
register them on the chat store without importing this service (M40-T01e).
Spec: docs/03-specs/12-sandbox-manager.md §4.2.
"""

from __future__ import annotations

from ar_common.sandbox_docker import (
    DockerSandboxLauncher,
    docker_available,
    image_present,
    start_sandbox,
    stop_sandbox,
)

__all__ = [
    "DockerSandboxLauncher",
    "docker_available",
    "image_present",
    "start_sandbox",
    "stop_sandbox",
]

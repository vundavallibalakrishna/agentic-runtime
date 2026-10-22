"""Docker driver. The socket is optional; the dev API keeps a local workspace."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def docker_available() -> bool:
    """True when the docker client can see a daemon. A missing socket is not fatal."""
    try:
        import aiodocker  # noqa: PLC0415
    except ImportError:
        return False
    try:
        client: Any = aiodocker.Docker()
    except Exception:  # noqa: BLE001 - a missing socket must not crash the process
        return False
    del client
    return True

"""Driver selection. An unisolated driver is refused unless the install allows it."""

import os

# Drivers that run a sandbox without kernel isolation. The docker driver shares the host
# kernel; an empty name runs the sandbox on the host itself.
_UNISOLATED = {"", "docker", "host"}


def selected_driver(*, allow_unisolated: bool) -> str:
    """``AR_SANDBOX_DRIVER`` when set, otherwise the isolated default.

    The isolated default is ``kubernetes`` (gVisor or Kata per the chart). Only an install
    that allows an unisolated sandbox (``AR_SANDBOX_ALLOW_UNISOLATED``) falls back to
    ``docker`` when no driver is named.
    """
    raw = os.environ.get("AR_SANDBOX_DRIVER", "").strip()
    if raw:
        return raw
    return "docker" if allow_unisolated else "kubernetes"


def assert_driver_allowed(driver: str, *, allow_unisolated: bool) -> None:
    """Fail closed when an unisolated driver is asked for and the install forbids it."""
    if driver.strip().lower() in _UNISOLATED and not allow_unisolated:
        raise RuntimeError(
            f"the {driver or 'host'!r} sandbox driver runs without kernel isolation; "
            "set AR_SANDBOX_ALLOW_UNISOLATED to allow it, or name an isolated driver "
            "in AR_SANDBOX_DRIVER"
        )

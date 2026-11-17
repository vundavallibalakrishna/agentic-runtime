"""Driver selection. The docker driver is the install default."""

import os


def selected_driver(*, allow_unisolated: bool) -> str:
    """``AR_SANDBOX_DRIVER`` when set, otherwise ``docker``.

    ``host`` runs the sandbox on the host and is refused unless the install sets
    ``AR_SANDBOX_ALLOW_UNISOLATED``. The docker driver is the supported driver.
    """
    del allow_unisolated
    raw = os.environ.get("AR_SANDBOX_DRIVER", "").strip().lower()
    if raw in {"", "docker"}:
        return "docker"
    return raw


def assert_driver_allowed(driver: str, *, allow_unisolated: bool) -> None:
    """Fail closed for an unknown driver, and for the host driver unless it is allowed."""
    name = driver.strip().lower()
    if name == "docker":
        return
    if name in {"", "host"} and allow_unisolated:
        return
    if name in {"", "host"}:
        raise RuntimeError(
            "the host sandbox driver runs without a container; "
            "set AR_SANDBOX_ALLOW_UNISOLATED to allow it, or leave AR_SANDBOX_DRIVER unset "
            "to use the docker driver"
        )
    raise RuntimeError(
        f"the {driver!r} sandbox driver is not supported; the install uses the docker driver"
    )

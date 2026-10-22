"""Driver selection. Docker is refused in production."""

import os


def selected_driver(env: str) -> str:
    """``AR_SANDBOX_DRIVER`` when set, otherwise docker outside production."""
    raw = os.environ.get("AR_SANDBOX_DRIVER", "").strip()
    if raw:
        return raw
    return "kubernetes" if env == "prod" else "docker"


def assert_driver_allowed(env: str, driver: str) -> None:
    """Fail closed when production is asked to run the docker driver."""
    if env == "prod" and driver == "docker":
        raise RuntimeError("docker driver is forbidden when AR_ENV=prod")

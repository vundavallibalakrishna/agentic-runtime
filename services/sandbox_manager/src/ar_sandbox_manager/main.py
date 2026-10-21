"""HTTP entrypoint for sandbox-manager."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8003


class Settings(BaseServiceSettings):
    service_name: str = "sandbox-manager"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("sandbox-manager", Settings())


def main() -> None:
    """Listen on ``AR_SANDBOX_MANAGER_HOST_PORT`` (default 8003)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_SANDBOX_MANAGER_HOST_PORT", LISTEN_PORT),
    )

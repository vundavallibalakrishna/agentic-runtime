"""HTTP entrypoint for sandbox-agent."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8080


class Settings(BaseServiceSettings):
    service_name: str = "sandbox-agent"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("sandbox-agent", Settings())


def main() -> None:
    """Listen on ``AR_SANDBOX_AGENT_HOST_PORT`` (default 8080)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_SANDBOX_AGENT_HOST_PORT", LISTEN_PORT),
    )

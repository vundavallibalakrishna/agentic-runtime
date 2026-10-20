"""HTTP entrypoint for mcp-gateway."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8002


class Settings(BaseServiceSettings):
    service_name: str = "mcp-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("mcp-gateway", Settings())


def main() -> None:
    """Listen on ``AR_MCPG_PORT`` (default 8002)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MCPG_PORT", LISTEN_PORT),
    )

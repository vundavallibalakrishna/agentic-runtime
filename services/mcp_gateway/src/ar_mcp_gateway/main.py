"""HTTP entrypoint for mcp-gateway."""

import uvicorn
from fastapi import FastAPI

from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8002


class Settings(BaseServiceSettings):
    service_name: str = "mcp-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("mcp-gateway", Settings())


def main() -> None:
    """Listen on port 8002."""
    uvicorn.run(create_application(), host="0.0.0.0", port=LISTEN_PORT)  # noqa: S104

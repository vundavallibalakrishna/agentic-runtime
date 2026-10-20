"""HTTP entrypoint for model-gateway."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8001


class Settings(BaseServiceSettings):
    service_name: str = "model-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("model-gateway", Settings())


def main() -> None:
    """Listen on ``AR_MG_PORT`` (default 8001)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MG_PORT", LISTEN_PORT),
    )

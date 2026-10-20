"""HTTP entrypoint for api."""

import uvicorn
from fastapi import FastAPI

from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8000


class Settings(BaseServiceSettings):
    service_name: str = "api"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("api", Settings())


def main() -> None:
    """Listen on port 8000."""
    uvicorn.run(create_application(), host="0.0.0.0", port=LISTEN_PORT)  # noqa: S104

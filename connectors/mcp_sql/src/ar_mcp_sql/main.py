"""HTTP entrypoint for mcp-sql."""

import uvicorn
from fastapi import FastAPI

from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

LISTEN_PORT = 8010


class Settings(BaseServiceSettings):
    service_name: str = "mcp-sql"


def create_application() -> FastAPI:
    """Build the ASGI app."""
    return create_app("mcp-sql", Settings())


def main() -> None:
    """Listen on port 8010."""
    uvicorn.run(create_application(), host="0.0.0.0", port=LISTEN_PORT)  # noqa: S104

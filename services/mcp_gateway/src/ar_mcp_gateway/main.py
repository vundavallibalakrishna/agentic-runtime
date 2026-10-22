"""HTTP entrypoint for mcp-gateway."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings, EnvName
from ar_common.web import create_app
from ar_domain.chat.service import ChatService
from ar_mcp_gateway.routes import router as tools_router

LISTEN_PORT = 8002


class Settings(BaseServiceSettings):
    service_name: str = "mcp-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app. The dev store is the same pipeline the API uses."""
    settings = Settings()
    app = create_app("mcp-gateway", settings)
    app.include_router(tools_router)
    app.state.chat = ChatService(allow_loopback=settings.env in {EnvName.DEV, EnvName.CI})
    return app


def main() -> None:
    """Listen on ``AR_MCPG_PORT`` (default 8002)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MCPG_PORT", LISTEN_PORT),
    )

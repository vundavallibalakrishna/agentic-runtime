"""HTTP entrypoint for mcp-gateway."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings, fake_models_allowed, loopback_allowed
from ar_common.web import create_app
from ar_domain.readmodel.boot import build_product_store
from ar_mcp_gateway.routes import router as tools_router

LISTEN_PORT = 8002


class Settings(BaseServiceSettings):
    service_name: str = "mcp-gateway"


def create_application() -> FastAPI:
    """Build the ASGI app. The dev store is the same pipeline the API uses."""
    settings = Settings()
    app = create_app("mcp-gateway", settings)
    app.include_router(tools_router)
    app.state.chat = build_product_store(
        settings,
        allow_loopback=loopback_allowed(settings),
        fake_models_allowed=fake_models_allowed(settings.env),
    )
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(app.state.chat, env=str(settings.env.value))
    return app


def main() -> None:
    """Listen on ``AR_MCPG_PORT`` (default 8002)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_MCPG_PORT", LISTEN_PORT),
    )

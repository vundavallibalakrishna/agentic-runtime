"""HTTP entrypoint for sandbox-manager."""

import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app
from ar_domain.chat.service import ChatService
from ar_sandbox_manager.drivers.base import assert_driver_allowed, selected_driver
from ar_sandbox_manager.routes import router as sandbox_router

LISTEN_PORT = 8003


class Settings(BaseServiceSettings):
    service_name: str = "sandbox-manager"


def create_application() -> FastAPI:
    """Build the ASGI app. Docker is refused when the environment is production."""
    settings = Settings()
    driver = selected_driver(settings.env.value)
    assert_driver_allowed(settings.env.value, driver)
    app = create_app("sandbox-manager", settings)
    app.include_router(sandbox_router)
    app.state.chat = ChatService()
    app.state.sandbox_driver = driver
    return app


def main() -> None:
    """Listen on ``AR_SANDBOX_MANAGER_HOST_PORT`` (default 8003)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_SANDBOX_MANAGER_HOST_PORT", LISTEN_PORT),
    )

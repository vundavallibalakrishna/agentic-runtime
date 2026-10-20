"""Shared container entrypoint. ``AR_APP_MODULE`` is an import path with ``create_application``."""

import importlib
import os

import uvicorn
from granian.constants import Interfaces
from granian.server import Server

from ar_common.settings import get_settings


def main() -> None:
    """Start the ASGI app named by ``AR_APP_MODULE`` on ``AR_PORT``."""
    module_name = os.environ["AR_APP_MODULE"]
    port = int(os.environ.get("AR_PORT", "8000"))
    module = importlib.import_module(module_name)
    app = module.create_application()
    settings = get_settings()
    if settings.asgi_server == "granian":
        server = Server(f"{module_name}:create_application", interface=Interfaces.ASGI, port=port)
        server.serve()
        return
    uvicorn.run(app, host="0.0.0.0", port=port)  # noqa: S104


if __name__ == "__main__":
    main()

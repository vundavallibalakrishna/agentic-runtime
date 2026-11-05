"""Serve the scripted model on a free loopback port from a thread, for a test session."""

import threading
import time
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from fastapi import FastAPI

_START_TIMEOUT_S = 15.0


class BackgroundServer:
    """A real HTTP server, so the code under test reaches the model as it does in production."""

    def __init__(self, app: FastAPI) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="stand-in", daemon=True)
        self.port = 0

    def start(self) -> int:
        """Start serving and return the port the kernel chose."""
        self._thread.start()
        deadline = time.monotonic() + _START_TIMEOUT_S
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("the scripted model server did not start")
            time.sleep(0.01)
        self.port = int(self._server.servers[0].sockets[0].getsockname()[1])
        return self.port

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)

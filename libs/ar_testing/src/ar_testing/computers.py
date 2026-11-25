"""Computers for tests: the product's own sandbox agent, started as a local process.

A tool that runs a command or keeps a file does it on the agent's computer, through the
sandbox agent. An install starts that agent in a container or a pod. A test starts the
same agent as a process on this machine, one for each computer, and the product reaches
it over HTTP exactly as it reaches a container. The container is what is missing, which
is why this lives in the test library: nothing here isolates what a command can touch.

The launcher has the two calls the product makes on any launcher: ``start`` and ``stop``.
"""

from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from typing import Any

_START = "from ar_sandbox_agent.main import main; main()"
_READY_S = 30.0


class LocalComputers:
    """Start and stop sandbox agents on loopback. One per computer, each in its own folder."""

    kind = "local"

    def __init__(self) -> None:
        self._running: dict[str, tuple[subprocess.Popen[bytes], Path]] = {}
        atexit.register(self.stop_all)

    def start(self, name: str, token: str, **labels: object) -> dict[str, object]:
        """Start the agent for one computer, in a folder of its own, and return its address."""
        del labels
        if name in self._running:
            self.stop(name)
        root = Path(tempfile.mkdtemp(prefix=f"{name}-"))
        (root / "workspace").mkdir()
        port = _free_port()
        env = dict(os.environ)
        env.update(
            {
                "AR_SANDBOX_ROOT": str(root),
                "AR_SANDBOX_TOKEN": token,
                "AR_SANDBOX_AGENT_HOST_PORT": str(port),
                "AR_ENV": "ci",
            }
        )
        process = subprocess.Popen(  # noqa: S603 — this interpreter, a fixed module
            [sys.executable, "-c", _START],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._running[name] = (process, root)
        endpoint = f"http://127.0.0.1:{port}"
        try:
            _wait_ready(endpoint, process)
        except RuntimeError:
            self.stop(name)
            raise
        return {"container_id": name, "endpoint_url": endpoint}

    def stop(self, name: str) -> None:
        """Stop one computer and remove its folder. Stopping one that is gone is fine."""
        found = self._running.pop(name, None)
        if found is None:
            return
        process, root = found
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        shutil.rmtree(root, ignore_errors=True)

    def stop_all(self) -> None:
        for name in list(self._running):
            self.stop(name)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(endpoint: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + _READY_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("the sandbox agent stopped while starting")
        try:
            if httpx.get(f"{endpoint}/healthz", timeout=1.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    raise RuntimeError("the sandbox agent did not start in time")


_shared: list[LocalComputers] = []


def local_computers() -> LocalComputers:
    """One launcher for the process. Its computers stop when the process ends."""
    if not _shared:
        _shared.append(LocalComputers())
    return _shared[0]


def give_computers(store: Any) -> None:
    """Let ``store`` start computers: each is the sandbox agent as a local process."""
    store.sandbox_launcher = local_computers()

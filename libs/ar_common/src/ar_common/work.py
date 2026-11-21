"""Shared worker entrypoint: several Temporal workers in one process.

``python -m ar_common.work ar_runtime.worker ar_system.worker`` runs each named module's
``run_worker`` coroutine beside one health server on ``AR_PORT``. A small install uses it
so two workers cost one process. Each worker keeps its own store and its own task queues,
exactly as when it runs alone; nothing is shared but the interpreter.

The modules are named on the command line and imported by name, as ``ar_common.serve``
does with ``AR_APP_MODULE``, so no service imports another.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import sys
from typing import TYPE_CHECKING

import uvicorn

from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

SERVICE_NAME = "worker"


class Settings(BaseServiceSettings):
    service_name: str = SERVICE_NAME


def runners(names: list[str]) -> list[Callable[[], Coroutine[object, object, None]]]:
    """The ``run_worker`` coroutine function of each module. A wrong name stops the start."""
    if not names:
        raise SystemExit("name at least one worker module, for example ar_runtime.worker")
    found = []
    for name in names:
        run = getattr(importlib.import_module(name), "run_worker", None)
        if not callable(run):
            raise SystemExit(f"{name} has no run_worker coroutine")
        found.append(run)
    return found


async def serve(
    runs: list[Callable[[], Coroutine[object, object, None]]], server: uvicorn.Server
) -> None:
    """Run the health server and every worker. They stop together.

    The health server ends on a stop signal; the workers are then cancelled so each one
    leaves through its own clean-up. A worker that ends on its own stops the process too:
    a container that is healthy while one of its workers is gone would hide the fault.
    """
    workers = [asyncio.create_task(run(), name=run.__module__) for run in runs]
    health = asyncio.create_task(server.serve(), name="health")
    done, _pending = await asyncio.wait([health, *workers], return_when=asyncio.FIRST_COMPLETED)
    server.should_exit = True
    for task in workers:
        task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(health, *workers, return_exceptions=True)
    for task in done:
        if task is not health and not task.cancelled() and task.exception() is not None:
            raise task.exception()  # type: ignore[misc]


def main() -> None:
    """Start the workers named on the command line, with one health server on ``AR_PORT``."""
    runs = runners(sys.argv[1:])
    config = uvicorn.Config(
        create_app(SERVICE_NAME, Settings()),
        host="0.0.0.0",  # noqa: S104
        port=int(os.environ.get("AR_PORT", "8012")),
    )
    asyncio.run(serve(runs, uvicorn.Server(config)))


if __name__ == "__main__":
    main()

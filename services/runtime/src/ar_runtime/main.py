"""Temporal worker entrypoint for runtime-worker. The worker loop arrives with its workflows."""

import asyncio

import temporalio.client
import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app
from ar_domain.db import metadata

LISTEN_PORT = 8012
TASK_QUEUE = "ar-runtime"


class Settings(BaseServiceSettings):
    service_name: str = "runtime-worker"


async def connect_temporal(address: str) -> temporalio.client.Client:
    """Open a Temporal client. Not called during health-only startup."""
    return await temporalio.client.Client.connect(address)


def create_application() -> FastAPI:
    """Health server. ``metadata`` keeps the domain dependency explicit."""
    _ = metadata
    return create_app("runtime-worker", Settings())


def main() -> None:
    """Listen on ``AR_RUNTIME_HOST_PORT`` (default 8012) and poll Temporal."""
    from ar_runtime.worker import run_worker  # noqa: PLC0415

    asyncio.run(_serve(run_worker))


async def _serve(worker: object) -> None:
    config = uvicorn.Config(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_RUNTIME_HOST_PORT", LISTEN_PORT),
    )
    server = uvicorn.Server(config)
    runner = worker() if callable(worker) else worker
    await asyncio.gather(server.serve(), runner)  # type: ignore[arg-type]

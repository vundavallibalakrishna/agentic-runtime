"""Temporal worker entrypoint for ingest-worker. The worker loop arrives with its workflows."""

import temporalio.client
import uvicorn
from fastapi import FastAPI

from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app
from ar_domain.db import metadata

LISTEN_PORT = 8014
TASK_QUEUE = "ar-ingest"


class Settings(BaseServiceSettings):
    service_name: str = "ingest-worker"


async def connect_temporal(address: str) -> temporalio.client.Client:
    """Open a Temporal client. Not called during health-only startup."""
    return await temporalio.client.Client.connect(address)


def create_application() -> FastAPI:
    """Health server. ``metadata`` keeps the domain dependency explicit."""
    _ = metadata
    return create_app("ingest-worker", Settings())


def main() -> None:
    """Listen on ``AR_INGEST_HOST_PORT`` (default 8014)."""
    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_INGEST_HOST_PORT", LISTEN_PORT),
    )

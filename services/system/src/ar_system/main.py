"""Temporal worker entrypoint for system-worker. The worker loop arrives with its workflows."""

import temporalio.client
import uvicorn
from fastapi import FastAPI

from ar_common.settings import BaseServiceSettings
from ar_common.web import create_app
from ar_domain.db import metadata

LISTEN_PORT = 8013
TASK_QUEUE = "ar-system"


class Settings(BaseServiceSettings):
    service_name: str = "system-worker"


async def connect_temporal(address: str) -> temporalio.client.Client:
    """Open a Temporal client. Not called during health-only startup."""
    return await temporalio.client.Client.connect(address)


def create_application() -> FastAPI:
    """Health server. ``metadata`` keeps the domain dependency explicit."""
    _ = metadata
    return create_app("system-worker", Settings())


def main() -> None:
    """Listen on port 8013."""
    uvicorn.run(create_application(), host="0.0.0.0", port=LISTEN_PORT)  # noqa: S104

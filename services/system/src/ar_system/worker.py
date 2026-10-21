"""Temporal worker entry. The health server stays up when Temporal is down."""

import asyncio

from temporalio.client import Client

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import get_settings

_log = get_logger(__name__)


async def run_worker() -> None:
    """Connect and poll ``ar-system``. Failures are logged and retried."""
    settings = get_settings()
    address = getattr(
        settings,
        "temporal_address",
        local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT"),
    )
    while True:
        try:
            client = await asyncio.wait_for(Client.connect(str(address)), timeout=0.5)
            _log.info("temporal_connected", address=address)
            del client
        except Exception as exc:  # noqa: BLE001 - keep the health server up
            _log.warning("temporal_unavailable", error=str(exc))
            await asyncio.sleep(5)
            continue
        return

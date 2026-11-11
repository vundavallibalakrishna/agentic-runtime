"""Keep a long activity alive. Temporal retries an activity that stops reporting."""

import asyncio
import contextlib
from typing import TYPE_CHECKING

from temporalio import activity

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_EVERY_S = 2


@contextlib.asynccontextmanager
async def heartbeating() -> AsyncIterator[None]:
    """Report to Temporal while the body runs. Outside an activity this does nothing."""
    task = asyncio.create_task(_beat()) if activity.in_activity() else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def _beat() -> None:
    while True:
        activity.heartbeat()
        await asyncio.sleep(_EVERY_S)

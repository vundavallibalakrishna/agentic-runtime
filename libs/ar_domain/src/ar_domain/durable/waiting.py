"""Wait a bounded time for a workflow a request started on a worker."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# How long a request waits for the worker before it answers with the row as it stands.
WORKER_WAIT_S = 120


async def worker_result(handle: Any, seconds: float) -> tuple[bool, object]:
    """``(True, result)`` when the workflow finished in time, ``(False, None)`` when not.

    Not finished covers two cases a caller treats the same way: the wait here ran out, and
    the workflow service ended its own long poll first (deadline exceeded, cancelled or
    unavailable). In both the worker carries on and writes the result itself. A workflow
    that failed raises, as it does from ``handle.result()``.
    """
    from temporalio.service import RPCError, RPCStatusCode  # noqa: PLC0415

    try:
        return True, await asyncio.wait_for(handle.result(), timeout=seconds)
    except TimeoutError:
        return False, None
    except RPCError as exc:
        if exc.status in {
            RPCStatusCode.DEADLINE_EXCEEDED,
            RPCStatusCode.CANCELLED,
            RPCStatusCode.UNAVAILABLE,
        }:
            return False, None
        raise

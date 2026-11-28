"""Run retrieval coroutines from synchronous callers."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, TypeVar, cast

from ar_common.offload import on_loop

if TYPE_CHECKING:
    from collections.abc import Awaitable

T = TypeVar("T")


def run_sync[T](awaitable: Awaitable[T]) -> T:
    """Finish one coroutine from synchronous code.

    A tool handler runs under ``ar_common.offload.run_sync`` on the process's loop thread.
    There the coroutine is handed to that loop, which goes on serving every other turn
    while it runs. It used to run on a loop of its own in a second thread while the
    process's loop stood still, so under parallel turns connections and heartbeats timed
    out. With no loop running it runs here. On a loop thread outside ``run_sync`` it can
    be neither awaited nor handed over, so it runs on a worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    handed, result = on_loop(awaitable)
    if handed:
        return cast("T", result)

    def _go() -> T:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_go).result()

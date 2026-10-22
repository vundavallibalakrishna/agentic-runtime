"""Run retrieval coroutines from synchronous callers."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable

T = TypeVar("T")


def run_sync[T](awaitable: Awaitable[T]) -> T:
    """Finish one coroutine. A live loop runs it on a worker thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    def _go() -> T:
        return asyncio.run(awaitable)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_go).result()

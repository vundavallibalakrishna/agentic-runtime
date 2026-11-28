"""A tool handler's retrieval runs on the process's loop, which goes on serving other turns.

``knowledge.syncutil.run_sync`` ran the coroutine on a new loop in a second thread and
held the process's loop until it finished. Under parallel eval turns the held loop timed
out connections and heartbeats, and the second loop could not use the pooled engine, so
each search opened its own connection. Proof: unit.
"""

import asyncio
import threading

from ar_common.offload import run_sync as run_handler
from ar_domain.knowledge.syncutil import run_sync


async def test_under_a_tool_handler_the_coroutine_runs_on_the_same_loop() -> None:
    loop = asyncio.get_running_loop()
    other_ran = asyncio.Event()

    async def retrieval() -> bool:
        await asyncio.wait_for(other_ran.wait(), 5.0)
        return asyncio.get_running_loop() is loop

    async def other_turn() -> None:
        other_ran.set()

    task = asyncio.create_task(other_turn())
    assert await run_handler(lambda: run_sync(retrieval())) is True
    await task


def test_with_no_loop_it_runs_in_place() -> None:
    async def retrieval() -> int:
        return threading.get_ident()

    assert run_sync(retrieval()) == threading.get_ident()


async def test_on_a_loop_outside_a_handler_it_runs_on_a_worker_thread() -> None:
    async def retrieval() -> int:
        return threading.get_ident()

    assert run_sync(retrieval()) != threading.get_ident()

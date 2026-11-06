"""A blocking call waits on a worker thread while the code around it stays on the loop thread."""

from __future__ import annotations

import asyncio
import contextvars
import threading
import time

import pytest

from ar_common.offload import CallTimedOutError, blocking, run_sync

REQUEST = contextvars.ContextVar("request", default="none")


async def test_the_loop_goes_on_while_synchronous_code_waits() -> None:
    ticks: list[float] = []

    async def heartbeat() -> None:
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.02)

    window: dict[str, float] = {}

    def handler() -> str:
        window["start"] = time.monotonic()
        blocking(time.sleep, 0.3)
        window["end"] = time.monotonic()
        return "done"

    beat = asyncio.create_task(heartbeat())
    assert await run_sync(handler) == "done"
    beat.cancel()
    # A held loop lets no tick happen between the start and the end of the wait. How
    # many happen depends on the machine, so the count is not what is checked.
    during = [tick for tick in ticks if window["start"] < tick < window["end"]]
    assert len(during) >= 2, "the loop was held while the handler waited"


async def test_only_the_wait_leaves_the_loop_thread() -> None:
    loop_thread = threading.get_ident()
    seen: dict[str, int] = {}

    def wait() -> int:
        seen["wait"] = threading.get_ident()
        return 7

    def handler(first: int, *, second: int) -> int:
        seen["before"] = threading.get_ident()
        got = blocking(wait)
        seen["after"] = threading.get_ident()
        return first + second + got

    assert await run_sync(handler, 1, second=2) == 10
    assert seen["before"] == seen["after"] == loop_thread, "the handler's own code moved"
    assert seen["wait"] != loop_thread


async def test_the_code_sees_the_callers_context_and_keeps_its_own_changes_to_itself() -> None:
    REQUEST.set("req-1")

    def handler() -> str:
        before = REQUEST.get()
        REQUEST.set("changed inside")
        return before

    assert await run_sync(handler) == "req-1"
    assert REQUEST.get() == "req-1"


async def test_an_error_in_the_wait_is_raised_where_the_code_called_it() -> None:
    def fails() -> None:
        raise OSError("connection refused")

    def handler() -> str:
        try:
            blocking(fails)
        except OSError as exc:
            return f"handled: {exc}"
        return "not raised"

    assert await run_sync(handler) == "handled: connection refused"

    def lets_it_out() -> None:
        blocking(fails)

    with pytest.raises(OSError, match="connection refused"):
        await run_sync(lets_it_out)


async def test_code_that_takes_too_long_is_stopped_at_its_wait_and_cleans_up() -> None:
    steps: list[str] = []

    def handler() -> None:
        try:
            blocking(time.sleep, 0.5)
            steps.append("finished")
        finally:
            steps.append("cleaned up")

    started = time.monotonic()
    with pytest.raises(CallTimedOutError) as caught:
        await run_sync(handler, limit_s=0.05)
    assert time.monotonic() - started < 0.4, "it waited for the slow call to end"
    assert caught.value.seconds == 0.05
    assert steps == ["cleaned up"]


async def test_the_time_limit_covers_every_wait_together() -> None:
    def handler() -> None:
        for _ in range(10):
            blocking(time.sleep, 0.03)

    with pytest.raises(CallTimedOutError):
        await run_sync(handler, limit_s=0.1)


async def test_cancelling_the_task_reaches_the_code() -> None:
    steps: list[str] = []

    def handler() -> None:
        try:
            blocking(time.sleep, 0.5)
        finally:
            steps.append("cleaned up")

    task = asyncio.create_task(run_sync(handler))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert steps == ["cleaned up"]


async def test_two_pieces_of_code_wait_at_the_same_time() -> None:
    spans: dict[str, tuple[float, float]] = {}

    def wait(name: str) -> None:
        began = time.monotonic()
        time.sleep(0.2)
        spans[name] = (began, time.monotonic())

    def handler(name: str) -> str:
        blocking(wait, name)
        return name

    got = await asyncio.gather(run_sync(handler, "a"), run_sync(handler, "b"))
    assert got == ["a", "b"]
    # Each wait began before the other ended: they ran at the same time, however
    # slowly the machine ran them.
    assert spans["a"][0] < spans["b"][1]
    assert spans["b"][0] < spans["a"][1]


def test_outside_run_sync_the_call_runs_in_place() -> None:
    here = threading.get_ident()
    assert blocking(threading.get_ident) == here
    assert blocking(lambda a, b=0: a + b, 2, b=3) == 5


async def test_on_the_loop_but_outside_run_sync_the_call_also_runs_in_place() -> None:
    assert blocking(threading.get_ident) == threading.get_ident()


async def test_code_with_no_wait_returns_its_value_and_its_error() -> None:
    assert await run_sync(lambda: 42) == 42

    def boom() -> None:
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        await run_sync(boom)

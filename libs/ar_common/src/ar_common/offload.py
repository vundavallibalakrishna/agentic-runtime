"""Let a slow call wait off the event loop while the code around it stays on the loop thread.

A tool handler is ordinary synchronous code. It reads and writes the process's store, which
has no locks because one thread owns it: the event loop's. When a handler made a network
call or ran a command, that thread stood still, so nothing else in the process moved: no
other conversation, no stream, no heartbeat, and a turn with a twenty-second tool call was
cancelled as dead.

Moving the handler to another thread would let it change the store while the loop reads it.
So the handler stays where it is and only its waiting moves. ``run_sync`` runs synchronous
code on the loop thread. Inside it, ``blocking(fn, ...)`` hands ``fn`` to a worker thread and
lets the loop go on until it returns. ``fn`` must only wait: a request, a subprocess, a
file. It must not touch the store.
"""

from __future__ import annotations

import asyncio
import contextvars
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import greenlet

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

_DEFAULT_THREADS = 16


class CallTimedOutError(Exception):
    """The synchronous code did not finish in the time ``run_sync`` gave it."""

    def __init__(self, seconds: float) -> None:
        super().__init__(f"the call did not finish within {seconds:g} seconds")
        self.seconds = seconds


# Greenlets started by ``run_sync``. Synchronous code runs in one, and ``blocking`` knows
# by this mark that there is a loop behind it to hand the wait to.
_MARK = "ar_run_sync"


_pool: list[ThreadPoolExecutor] = []


def _threads() -> int:
    raw = os.environ.get("AR_TOOL_WORKER_THREADS", "").strip()
    return max(1, int(raw)) if raw.isdigit() else _DEFAULT_THREADS


def _executor() -> ThreadPoolExecutor:
    if not _pool:
        _pool.append(ThreadPoolExecutor(max_workers=_threads(), thread_name_prefix="tool-io"))
    return _pool[0]


async def run_sync(
    fn: Callable[..., Any], /, *args: object, limit_s: float | None = None, **kwargs: object
) -> Any:
    """Run ``fn`` on this thread, letting the loop go on wherever ``fn`` calls ``blocking``.

    ``limit_s`` is for the whole of ``fn``. When it passes while ``fn`` waits in a
    ``blocking`` call, ``CallTimedOutError`` is raised inside ``fn`` at that call, so its
    own clean-up runs. The worker thread's late result is dropped. Cancelling the task
    reaches ``fn`` the same way.
    """
    deadline = None if limit_s is None else time.monotonic() + limit_s
    bridge = greenlet.greenlet(lambda: fn(*args, **kwargs))
    # The code sees the context variables of the coroutine that started it.
    bridge.gr_context = contextvars.copy_context()
    setattr(bridge, _MARK, True)
    waiting = bridge.switch()
    while not bridge.dead:
        try:
            value = await _within(waiting, deadline, limit_s)
        except BaseException as exc:  # noqa: BLE001 - handed to the code that was waiting
            waiting = bridge.throw(exc)
        else:
            waiting = bridge.switch(value)
    return waiting


async def _within(waiting: Awaitable[Any], deadline: float | None, limit_s: float | None) -> Any:
    if deadline is None or limit_s is None:
        return await waiting
    try:
        async with asyncio.timeout_at(asyncio.get_running_loop().time() + _left(deadline)):
            return await waiting
    except TimeoutError:
        raise CallTimedOutError(limit_s) from None


def _left(deadline: float) -> float:
    return max(deadline - time.monotonic(), 0.0)


def blocking[T](fn: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Call ``fn``, which only waits, without holding the event loop while it does.

    Under ``run_sync`` the call runs on a worker thread and the loop serves everything
    else meanwhile. Anywhere else (a script, a test, a thread with no loop) it runs in
    place, so code that uses this behaves the same wherever it is called from.
    """
    current = greenlet.getcurrent()
    if not getattr(current, _MARK, False) or current.parent is None:
        return fn(*args, **kwargs)
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_executor(), lambda: fn(*args, **kwargs))
    result: T = current.parent.switch(future)
    return result


def blocking_all[T](calls: Sequence[Callable[[], T]]) -> list[T]:
    """Run several calls that only wait, at the same time, and return their results in order.

    Under ``run_sync`` each call goes to a worker thread and the loop goes on until all
    have returned; the pool's size bounds how many wait at once. Anywhere else they run
    one after another, in place. The first failure is raised once every call has ended.
    """
    current = greenlet.getcurrent()
    if not getattr(current, _MARK, False) or current.parent is None:
        return [call() for call in calls]
    loop = asyncio.get_running_loop()
    pending = [loop.run_in_executor(_executor(), call) for call in calls]
    done: list[T | BaseException] = current.parent.switch(
        asyncio.gather(*pending, return_exceptions=True)
    )
    for item in done:
        if isinstance(item, BaseException):
            raise item
    return [item for item in done if not isinstance(item, BaseException)]

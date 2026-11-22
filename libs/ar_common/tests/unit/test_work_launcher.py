"""Several workers in one process: each runs, and they stop together."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from ar_common import work


class _Health:
    """Stands in for the health server: runs until told to exit."""

    def __init__(self) -> None:
        self.should_exit = False

    async def serve(self) -> None:
        while not self.should_exit:  # noqa: ASYNC110
            await asyncio.sleep(0.01)


def _module(name: str, run: object) -> None:
    module = types.ModuleType(name)
    module.run_worker = run  # type: ignore[attr-defined]
    sys.modules[name] = module


def test_each_named_worker_runs_and_all_stop_with_the_health_server() -> None:
    started: list[str] = []
    stopped: list[str] = []

    def worker(label: str):  # type: ignore[no-untyped-def]
        async def run() -> None:
            started.append(label)
            try:
                await asyncio.Event().wait()
            finally:
                stopped.append(label)

        return run

    _module("work_test_one", worker("one"))
    _module("work_test_two", worker("two"))
    runs = work.runners(["work_test_one", "work_test_two"])
    health = _Health()

    async def scenario() -> None:
        task = asyncio.create_task(work.serve(runs, health))  # type: ignore[arg-type]
        for _ in range(100):
            if len(started) == 2:
                break
            await asyncio.sleep(0.01)
        health.should_exit = True
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())
    assert sorted(started) == ["one", "two"]
    assert sorted(stopped) == ["one", "two"]


def test_a_worker_that_fails_stops_the_process_with_its_error() -> None:
    async def broken() -> None:
        raise RuntimeError("worker is gone")

    async def steady() -> None:
        await asyncio.Event().wait()

    _module("work_test_broken", broken)
    _module("work_test_steady", steady)
    runs = work.runners(["work_test_broken", "work_test_steady"])
    with pytest.raises(RuntimeError, match="worker is gone"):
        asyncio.run(asyncio.wait_for(work.serve(runs, _Health()), timeout=2))  # type: ignore[arg-type]


def test_a_wrong_module_name_stops_the_start() -> None:
    _module("work_test_empty", None)
    with pytest.raises(SystemExit, match="no run_worker"):
        work.runners(["work_test_empty"])
    with pytest.raises(SystemExit, match="at least one"):
        work.runners([])

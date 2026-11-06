"""A tool call does not hold the event loop (M38-T09, finding F11).

A handler that fetched a page or ran a command stopped the whole process while it waited.
On the live tenant a twenty-second summary stopped the worker's heartbeat, and the turn was
cancelled and run three times. The handler now stays on the loop thread, where the store
is safe to use, and only its waiting moves to a worker thread.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
import uuid
from pathlib import Path

from ar_common.offload import run_sync
from ar_domain.demo_ids import demo_id
from ar_domain.tools import general
from ar_domain.tools.general import dispatch_general
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

SOURCE = Path(__file__).resolve().parents[2] / "src" / "ar_domain"


def _who() -> dict[str, object]:
    return {"_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin"), "_run_id": uuid.uuid4()}


def _request(store: object, qualified: str, arguments: dict[str, object]) -> dict[str, object]:
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == qualified
    )
    return {
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "synthetic": True,
        "tool_version_id": version["id"],
        "arguments": arguments,
        "model_call_id": "m38-t09",
    }


async def _ticks_while(work: object) -> tuple[object, int]:
    """Await ``work`` and count how often another coroutine ran meanwhile."""
    count = 0

    async def tick() -> None:
        nonlocal count
        while True:
            count += 1
            await asyncio.sleep(0.02)

    ticker = asyncio.create_task(tick())
    try:
        return await work, count  # type: ignore[misc]
    finally:
        ticker.cancel()


async def test_another_coroutine_runs_while_a_command_does() -> None:
    store = demo_store()
    request = _request(store, "general.shell", {"command": "sleep 0.5; echo finished"})
    result, ticks = await _ticks_while(run_sync(ToolPipeline(store).execute, request))
    assert result["status"] == "succeeded", result
    assert "finished" in str(result["result_preview"])
    assert ticks >= 12, f"the loop ran {ticks} times in half a second: it was held"


async def test_the_handler_stays_on_the_loop_thread_and_only_the_command_leaves(
    monkeypatch: object,
) -> None:
    store = demo_store()
    loop_thread = threading.get_ident()
    seen: dict[str, int] = {}
    run_command = general.run_isolated
    keep_file = general._store_file

    def command(*args: object, **kwargs: object) -> object:
        seen["command"] = threading.get_ident()
        return run_command(*args, **kwargs)  # type: ignore[arg-type]

    def file(*args: object, **kwargs: object) -> object:
        seen["store"] = threading.get_ident()
        return keep_file(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(general, "run_isolated", command)  # type: ignore[attr-defined]
    monkeypatch.setattr(general, "_store_file", file)  # type: ignore[attr-defined]
    ran = await run_sync(
        dispatch_general, store, "code", {**_who(), "source": "open('out.txt', 'w').write('x')"}
    )
    assert ran["is_error"] is False, ran["text"]
    assert seen["command"] != loop_thread, "the command held the loop thread"
    assert seen["store"] == loop_thread, "the store was written from another thread"


async def test_a_call_that_outlives_the_runs_time_is_stopped_and_says_so() -> None:
    store = demo_store()
    request = _request(store, "general.shell", {"command": "sleep 3; echo late"})
    started = time.monotonic()
    result = await run_sync(ToolPipeline(store).execute, request, limit_s=0.4)
    assert time.monotonic() - started < 2.0, "the call was waited for"
    assert result["status"] == "failed"
    assert result["error"]["code"] == "upstream_timeout"
    told = str(result["result_preview"])
    assert "did not finish within 0.4 seconds" in told
    assert "check before calling it again" in told
    assert "late" not in told


def test_outside_the_loop_a_tool_call_works_as_before() -> None:
    """A script or a scripted turn calls the pipeline directly: the call runs in place."""
    store = demo_store()
    result = ToolPipeline(store).execute(
        _request(store, "general.shell", {"command": "echo in place"})
    )
    assert result["status"] == "succeeded"
    assert "in place" in str(result["result_preview"])


# Calls that wait: a request, a command, a sleep. In the code a tool call runs through,
# each goes through ``blocking`` so that it waits on a worker thread.
_WAITS = re.compile(
    r"(?<![\w.])(?:httpx\.(?:get|post|put|request)|subprocess\.run|time\.sleep"
    r"|run_isolated|(?:client|http)\.(?:get|post|put|request))\("
)
_TOOL_PATHS = (
    "tools",
    "documents",
    "connectors",
    "sandboxes",
    "models/embedding.py",
    "policy/engine.py",
)


def test_no_tool_code_waits_on_the_loop_thread() -> None:
    found: list[str] = []
    for part in _TOOL_PATHS:
        target = SOURCE / part
        files = [target] if target.is_file() else sorted(target.rglob("*.py"))
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                # A definition, an import, a call already inside ``blocking(lambda: ...)``,
                # and an awaited call on an async client do not hold the loop.
                if any(mark in code for mark in ("def ", "lambda: ", "import ", "await ")):
                    continue
                if _WAITS.search(code):
                    found.append(f"{path.relative_to(SOURCE)}:{number}: {line.strip()}")
    assert found == [], "these calls wait on the loop thread; wrap them in blocking(...)"

"""One Temporal test server and the real runtime worker.

Unit tests that start a run use this client. The worker polls the same workflows
and activities as ``runtime-worker``. There is no in-process turn engine.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

if TYPE_CHECKING:
    from collections.abc import Iterator
    from concurrent.futures import Future


class TemporalBridge:
    """A client whose calls run on the worker thread's loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.error: BaseException | None = None
        self.env: WorkflowEnvironment | None = None
        self.client: Any = None
        self._workers: list[Worker] = []
        self._tasks: list[asyncio.Task[None]] = []
        self._thread = threading.Thread(target=self._run, name="temporal-test", daemon=True)

    def start(self) -> None:
        self._thread.start()
        if not self.ready.wait(180):
            raise RuntimeError("Temporal test server did not start")
        if self.error is not None:
            raise RuntimeError("Temporal test server did not start") from self.error

    def stop(self) -> None:
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=10)

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._boot())
        except BaseException as exc:  # noqa: BLE001 - surface the boot error to the fixture
            self.error = exc
            self.ready.set()
            return
        self.ready.set()
        self.loop.run_forever()
        self.loop.close()

    async def _boot(self) -> None:
        last: BaseException | None = None
        for attempt in range(3):
            try:
                # Local, not time-skipping: an approval wait must not expire
                # while a test is still deciding.
                self.env = await WorkflowEnvironment.start_local()
                break
            except RuntimeError as exc:
                last = exc
                if "ephemeral server download" not in str(exc) or attempt == 2:
                    raise
                await asyncio.sleep(1 + attempt)
        if self.env is None:
            raise RuntimeError("Temporal test server did not start") from last
        self.client = self.env.client
        from ar_ingest.main import TASK_QUEUE as INGEST_QUEUE  # noqa: PLC0415
        from ar_ingest.worker import ingest_activities, ingest_workflows  # noqa: PLC0415
        from ar_runtime.main import TASK_QUEUE  # noqa: PLC0415
        from ar_runtime.worker import runtime_activities, runtime_workflows  # noqa: PLC0415
        from ar_system.workflows.eval_run import (  # noqa: PLC0415
            EVAL_QUEUE,
            EvalRunWorkflow,
            execute_eval_activity,
        )

        runtime = Worker(
            self.client,
            task_queue=TASK_QUEUE,
            workflows=runtime_workflows(),
            activities=runtime_activities(),
        )
        evals = Worker(
            self.client,
            task_queue=EVAL_QUEUE,
            workflows=[EvalRunWorkflow],
            activities=[execute_eval_activity],
        )
        ingest = Worker(
            self.client,
            task_queue=INGEST_QUEUE,
            workflows=ingest_workflows(),
            activities=ingest_activities(),
        )
        self._workers = [runtime, evals, ingest]
        for worker in self._workers:
            self._tasks.append(asyncio.create_task(worker.run()))

    def submit(self, coro: Any) -> Future[Any]:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


class RuntimeClient:
    """Per-store client. Starting or signalling a run binds that store for the worker."""

    def __init__(self, store: object, bridge: TemporalBridge) -> None:
        self.store = store
        self.bridge = bridge

    def _bind(self) -> None:
        from ar_ingest.activities import bind_store as bind_ingest  # noqa: PLC0415
        from ar_runtime.activities.expire_approval import bind_store as bind_runtime  # noqa: PLC0415
        from ar_system.routines_store import bind_store as bind_system  # noqa: PLC0415

        bind_runtime(self.store)
        bind_system(self.store)
        bind_ingest(self.store)

    async def start_workflow(self, workflow: object, arg: object, **kwargs: object) -> object:
        self._bind()
        client = self.bridge.client
        future = self.bridge.submit(client.start_workflow(workflow, arg, **kwargs))
        return await asyncio.wrap_future(future)

    def get_workflow_handle(self, workflow_id: str) -> _Handle:
        return _Handle(self.bridge, workflow_id)


class _Handle:
    def __init__(self, bridge: TemporalBridge, workflow_id: str) -> None:
        self.bridge = bridge
        self.workflow_id = workflow_id

    def _real(self) -> Any:
        return self.bridge.client.get_workflow_handle(self.workflow_id)

    async def signal(self, name: str, *args: object) -> object:
        future = self.bridge.submit(self._real().signal(name, *args))
        return await asyncio.wrap_future(future)

    async def describe(self) -> object:
        future = self.bridge.submit(self._real().describe())
        return await asyncio.wrap_future(future)

    async def result(self) -> object:
        future = self.bridge.submit(self._real().result())
        return await asyncio.wrap_future(future)


def _install(bridge: TemporalBridge) -> None:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415

    original = ChatService.__init__

    def _init(self: ChatService, *args: object, **kwargs: object) -> None:
        original(self, *args, **kwargs)  # type: ignore[arg-type]
        if self.temporal_client is None:
            self.temporal_client = RuntimeClient(self, bridge)

    ChatService.__init__ = _init  # type: ignore[method-assign]


@pytest.fixture(scope="session", autouse=True)
def temporal_runtime() -> Iterator[TemporalBridge]:
    """Boot the test server once. Every new chat store talks to this worker."""
    bridge = TemporalBridge()
    bridge.start()
    _install(bridge)
    yield bridge
    bridge.stop()

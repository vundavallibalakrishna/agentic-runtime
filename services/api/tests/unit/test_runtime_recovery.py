"""Worker cancellation and transaction boundaries remain safe under races."""

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from temporalio.service import RPCError, RPCStatusCode

from ar_api.deps import get_tenant_writer
from ar_api.middleware.durable import DurableMiddleware
from ar_api.routers.m2 import cancel_run
from ar_common.errors import NotFoundError, UnavailableError
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.db.context import Principal
from ar_testing.demo import demo_store


def request_for(store: ChatService, user: str = "admin") -> Request:
    principal = Principal(kind="user", id=str(demo_id(user)), tenant_id=demo_id("tenant"))
    app = SimpleNamespace(state=SimpleNamespace(chat=store, settings=SimpleNamespace()))
    return Request(
        {"type": "http", "app": app, "state": {"principal": principal, "request_id": "req-test"}}
    )


@pytest.mark.parametrize("outcome", ["signal", "completed", "unavailable", "wrong_owner"])
async def test_temporal_cancel_races_and_ownership(
    outcome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = demo_store()
    conv = store.create_conversation(demo_id("tenant"), demo_id("admin"), None)
    posted = store.post_message(
        demo_id("tenant"),
        demo_id("admin"),
        uuid.UUID(str(conv["id"])),
        "slow reply",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    store.runs[run_id]["temporal_workflow_id"] = "test-run"
    signal = AsyncMock()
    store.temporal_client = SimpleNamespace(
        get_workflow_handle=lambda key: SimpleNamespace(signal=signal)
    )
    if outcome in {"completed", "unavailable"}:
        signal.side_effect = RPCError("workflow unavailable", RPCStatusCode.NOT_FOUND, b"")

    async def reload(*args: object) -> None:
        if outcome == "completed":
            store.runs[run_id]["status"] = "completed"

    monkeypatch.setattr("ar_domain.durable.hydrate.reload_run", reload)
    request = request_for(store, "member" if outcome == "wrong_owner" else "admin")
    if outcome == "wrong_owner":
        with pytest.raises(NotFoundError):
            await cancel_run(run_id, request)
        signal.assert_not_called()
    elif outcome == "unavailable":
        with pytest.raises(UnavailableError):
            await cancel_run(run_id, request)
    else:
        result = await cancel_run(run_id, request)
        assert result["status"] == ("completed" if outcome == "completed" else "queued")
        signal.assert_awaited_once_with("cancel")


async def test_durable_commit_failure_prevents_success_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    store._bind_attempted = True
    sent = []

    async def app(scope: object, receive: object, send: object) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})

    flush = AsyncMock(side_effect=RuntimeError("transaction rolled back"))
    monkeypatch.setattr("ar_domain.durable.flush.flush_store", flush)

    async def send(message: object) -> None:
        sent.append(message)

    with pytest.raises(RuntimeError, match="rolled back"):
        await DurableMiddleware(app)(request_for(store).scope, AsyncMock(), send)
    assert sent == []


async def test_tenant_writer_uses_only_authenticated_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = []

    @asynccontextmanager
    async def platform(reason: str):
        opened.append(reason)
        yield SimpleNamespace()

    monkeypatch.setattr("ar_api.deps.platform_session", platform)
    request = request_for(demo_store())
    async for service in get_tenant_writer(request):
        assert service.store.ctx.tenant_id == demo_id("tenant")
        assert service.store.ctx.user_id == demo_id("admin")
    assert opened == [f"tenant settings update: {demo_id('tenant')}"]


class _Workflows:
    """Temporal as the API asks it at start: the ids of the workflows still going."""

    def __init__(self, going: set[str]) -> None:
        self.going = going

    def get_workflow_handle(self, workflow_id: str) -> _Workflows._Handle:
        return _Workflows._Handle(workflow_id in self.going)

    class _Handle:
        def __init__(self, going: bool) -> None:
            self.going = going

        async def describe(self) -> object:
            from types import SimpleNamespace

            from temporalio.service import RPCError, RPCStatusCode

            if not self.going:
                raise RPCError("workflow not found", RPCStatusCode.NOT_FOUND, b"")
            return SimpleNamespace(status=SimpleNamespace(name="RUNNING"))


async def test_an_api_that_starts_ends_a_lost_run_and_leaves_one_a_worker_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_api.middleware.durable import _end_lost_runs
    from ar_domain.chat.service import ChatService

    saved: list[object] = []

    async def flush(store: object) -> None:
        saved.append(store)

    monkeypatch.setattr("ar_domain.durable.flush.flush_store", flush)
    store = ChatService()
    held, lost = uuid.uuid4(), uuid.uuid4()
    for run_id in (held, lost):
        store.runs[run_id] = {"id": run_id, "tenant_id": uuid.uuid4(), "status": "running"}
    store.temporal_client = _Workflows({f"run-{held}"})  # type: ignore[assignment]
    await _end_lost_runs(store)
    assert store.runs[held]["status"] == "running"
    assert store.runs[lost]["status"] == "failed"
    assert store.runs[lost]["error"]["code"] == "interrupted"
    # What it ended is saved at once, and a start that ends nothing writes nothing.
    assert saved == [store]
    await _end_lost_runs(store)
    assert saved == [store]

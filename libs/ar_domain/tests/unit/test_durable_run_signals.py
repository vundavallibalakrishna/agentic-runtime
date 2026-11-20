"""Approvals signal the run. Eval runs are queued on Temporal. Ingestion jobs are tracked."""

import uuid

import pytest

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.durable.tracking import BUCKETS, install_tracking
from ar_domain.evals.book import EvalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import connect_chat, demo_store


class _Temporal:
    def __init__(self) -> None:
        self.started: list[tuple[object, object, str]] = []
        self.signals: list[tuple[str, object]] = []

    async def start_workflow(self, workflow: object, payload: object, **kwargs: object) -> None:
        self.started.append((workflow, payload, kwargs.get("task_queue")))

    def get_workflow_handle(self, _workflow_id: str) -> _Temporal:
        return self

    async def signal(self, name: str, payload: object = None) -> None:
        self.signals.append((name, payload))


def test_an_approval_signals_and_does_not_call_the_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.approvals.pending import hold
    from ar_domain.tools import resume

    store = demo_store()
    temporal = _Temporal()
    store.temporal_client = temporal
    called: list[object] = []
    monkeypatch.setattr(
        "ar_domain.tools.gateway_client.execute_tool",
        lambda _store, _request: called.append(True),
    )
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "write it", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    approval_id = uuid.uuid4()
    run["status"] = "waiting_approval"
    hold(run, {"approval_id": approval_id, "arguments": {}})
    store.approvals[approval_id] = {
        "id": approval_id,
        "run_id": run["id"],
        "status": "approved",
        "tenant_id": tenant,
    }
    resume.settle_approval(store, store.approvals[approval_id])
    assert called == []
    assert temporal.signals == [
        ("approval_decided", {"status": "approved", "approval_id": str(approval_id)})
    ]
    assert run["status"] == "waiting_approval"


@pytest.mark.asyncio
async def test_eval_runs_are_deferred_to_temporal() -> None:
    store = demo_store()
    connect_chat(store, demo_id("tenant"))
    temporal = _Temporal()
    store.temporal_client = temporal
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
    )
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Deferred", "kind": "functional"})
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "hello",
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "Say hello"}],
        },
    )
    queued = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    assert queued["status"] == "queued"
    await _wait(store)
    assert temporal.started
    assert temporal.started[0][0] == "EvalRunWorkflow"
    assert temporal.started[0][2] == "ar-eval"
    assert store.eval_runs[uuid.UUID(str(queued["id"]))]["status"] == "queued"


def test_ingestion_jobs_are_a_tracked_bucket() -> None:
    assert "ingestion_jobs" in BUCKETS
    store = demo_store()
    install_tracking(store)
    job_id = uuid.uuid4()
    store.ingestion_jobs[job_id] = {
        "id": job_id,
        "tenant_id": demo_id("tenant"),
        "status": "running",
    }
    assert job_id in store.ingestion_jobs.dirty


def test_a_decision_continues_or_stops_and_cancel_is_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_domain.approvals.pending import hold
    from ar_domain.tools.resume import apply_decision, mark_cancelled
    from ar_domain.tools.worker_loop import snapshot, write_worker_loop

    store = demo_store()
    monkeypatch.setattr(
        "ar_domain.tools.gateway_client.execute_tool",
        lambda _store, _request: {"status": "succeeded", "result_preview": "wrote"},
    )
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "write it", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    assert apply_decision(store, run, {"status": "input"}) == "continue"
    run["status"] = "waiting_input"
    assert apply_decision(store, run, {"status": "input", "text": "blue"}) == "continue"
    assert run["resume_answer"] == "blue"
    run["status"] = "waiting_input"
    run["pending_question_id"] = uuid.uuid4()
    assert apply_decision(store, run, {"status": "input", "text": "no-row"}) == "continue"
    assert run["status"] == "running"
    run["status"] = "waiting_approval"
    hold(run, {"approval_id": uuid.uuid4(), "model_call_id": uuid.uuid4()})
    assert apply_decision(store, run, {"status": "rejected"}) == "final"
    assert run["status"] == "completed"
    run["status"] = "waiting_approval"
    write_worker_loop(
        run,
        snapshot(
            messages=[],
            steps=1,
            used_calls=0,
            tokens=1,
            tokens_in=1,
            tokens_out=0,
            prompt_seen=1,
            cost=0,
            previews=[],
            elapsed_s=0,
            user_text="write it",
            repairs=0,
            consecutive_errors=0,
            planned=True,
            failed_open=False,
            phase="tools",
            pending_calls=[{"id": "c1", "name": "files.write"}],
        ),
    )
    approval_id = uuid.uuid4()
    hold(run, {"approval_id": approval_id, "model_call_id": uuid.uuid4()})
    store.approvals[approval_id] = {
        "id": approval_id,
        "status": "approved",
        "run_id": run["id"],
        "tenant_id": tenant,
    }
    assert apply_decision(store, run, {"status": "approved"}) == "continue"
    assert run["status"] == "running"
    mark_cancelled(store, run)
    assert run["status"] == "cancelled"
    mark_cancelled(store, run)
    assert run["status"] == "cancelled"
    store.temporal_client = None
    other = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "again", schedule=False
    )
    waiting = store.runs[uuid.UUID(str(other["run"]["id"]))]
    waiting["status"] = "waiting_approval"
    held_id = uuid.uuid4()
    hold(waiting, {"approval_id": held_id})
    from ar_domain.tools.resume import settle_approval

    settle_approval(store, {"id": held_id, "run_id": waiting["id"], "status": "approved"})
    assert waiting["status"] == "failed"
    error = waiting.get("error")
    assert isinstance(error, dict)
    assert error["reason"] == "not_resumed"


@pytest.mark.asyncio
async def test_a_worker_step_cancels_applies_and_fans_out(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.approvals.pending import hold
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = demo_store()
    bind_store(store)
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "What do the notes say about a kite?",
        research=True,
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    first = await advance_chat_step({"run_id": str(run_id), "text": "kites"})
    assert first["kind"] in {"fanout", "model", "final", "paused"}
    run = store.runs[run_id]
    run["status"] = "running"
    run["cancel_requested"] = True
    cancelled = await advance_chat_step({"run_id": str(run_id)})
    assert cancelled["status"] == "cancelled"
    fresh = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "write", schedule=False
    )
    waiting_id = uuid.UUID(str(fresh["run"]["id"]))
    waiting = store.runs[waiting_id]
    waiting["status"] = "waiting_approval"
    approval_id = uuid.uuid4()
    hold(waiting, {"approval_id": approval_id, "model_call_id": uuid.uuid4()})
    monkeypatch.setattr(
        "ar_domain.tools.gateway_client.execute_tool",
        lambda _store, _request: {"status": "succeeded", "result_preview": "wrote"},
    )
    decided = await advance_chat_step(
        {
            "run_id": str(waiting_id),
            "decision": {"status": "approved", "approval_id": str(approval_id)},
        }
    )
    assert decided["kind"] == "final"
    missing = await advance_chat_step({"run_id": str(uuid.uuid4())})
    assert missing["status"] == "missing"


@pytest.mark.asyncio
async def test_eval_schedule_stays_queued_when_temporal_refuses() -> None:
    store = demo_store()
    connect_chat(store, demo_id("tenant"))

    class _Down:
        async def start_workflow(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("frontend down")

    store.temporal_client = _Down()
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
    )
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Fallback", "kind": "functional"})
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "hello",
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "Say hello"}],
        },
    )
    queued = book.start_run(actor, suite["id"], {"agent_version_ref": "published"})  # type: ignore[arg-type]
    await _wait(store)
    assert store.eval_runs[uuid.UUID(str(queued["id"]))]["status"] == "queued"


async def test_an_ingestion_job_is_written() -> None:
    from ar_domain.durable.flush import _ingestion_jobs

    seen: list[dict[str, object]] = []

    class _Session:
        async def execute(
            self, _statement: object, params: dict[str, object] | None = None
        ) -> None:
            if params:
                seen.append(params)

    job_id = uuid.uuid4()
    tenant = demo_id("tenant")
    await _ingestion_jobs(
        _Session(),  # type: ignore[arg-type]
        [
            {"id": "not-a-uuid"},
            {
                "id": job_id,
                "tenant_id": tenant,
                "collection_id": uuid.uuid4(),
                "source_id": uuid.uuid4(),
                "kind": "full_sync",
                "status": "succeeded",
                "temporal_workflow_id": f"full_sync-{job_id}",
                "stats": {"seen": 1},
                "error": None,
                "triggered_by": "manual",
                "started_at": None,
                "finished_at": None,
                "created_at": None,
            },
        ],
    )
    assert seen and seen[0]["id"] == job_id
    assert seen[0]["kind"] == "full_sync"


def test_signal_and_budget_without_a_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from ar_domain.runs.dispatch import request_signal, workflow_payload

    class _Handle:
        def __init__(self) -> None:
            self.called: list[str] = []

        async def signal(self, name: str, _payload: object = None) -> None:
            self.called.append(name)

    class _Client:
        def __init__(self) -> None:
            self.handle = _Handle()

        def get_workflow_handle(self, _workflow_id: str) -> _Handle:
            return self.handle

    store = demo_store()
    client = _Client()
    store.temporal_client = client
    assert request_signal(store, uuid.uuid4(), "cancel", {}) is True
    assert client.handle.called == ["cancel"]

    class _NoSignal:
        def get_workflow_handle(self, _workflow_id: str) -> object:
            return object()

    store.temporal_client = _NoSignal()
    assert request_signal(store, uuid.uuid4(), "cancel", {}) is False

    class _Settings:
        run_history_steps = "nope"
        approval_wait_s = True

    def _settings() -> _Settings:
        return _Settings()

    monkeypatch.setattr("ar_common.settings.get_settings", _settings)
    run_id = uuid.uuid4()
    research = {
        "trigger": "research",
        "checkpoint": {"research": {"question": "q", "max_steps": 3}},
    }
    asked = workflow_payload(store, research, run_id, "q")
    assert asked["max_steps"] >= 1
    assert asked["step_timeout_s"] == 120
    chat = workflow_payload(store, {"agent_version_id": uuid.uuid4()}, run_id, "hi")
    assert chat["history_steps"] == 24
    assert chat["wait_s"] == 86400
    # Activities, not model calls: the default budget is 16 model calls and 16 tool calls,
    # and a tool call that waits for approval takes one more activity.
    assert chat["max_steps"] == 16 + 2 * 16
    # One activity may last as long as the run's wall clock allows, and a little more.
    assert chat["step_timeout_s"] == 600 + 60
    hurried = workflow_payload(
        store,
        {"agent_version_id": uuid.uuid4(), "budget_override": {"max_wall_clock_s": 30}},
        run_id,
        "hi",
    )
    assert hurried["step_timeout_s"] == 30 + 60
    from ar_domain.tools.resume import _approval_row, _resume, apply_decision, settle_approval

    settle_approval(store, {"id": uuid.uuid4(), "run_id": uuid.uuid4(), "status": "approved"})
    idle = {"id": uuid.uuid4(), "status": "completed", "checkpoint": {}}
    assert apply_decision(store, idle, {"status": "approved"}) == "continue"
    held_id = uuid.uuid4()
    waiting = {
        "id": held_id,
        "status": "waiting_approval",
        "checkpoint": {},
        "tenant_id": demo_id("tenant"),
        "conversation_id": "",
    }
    store.runs[held_id] = waiting
    assert apply_decision(store, waiting, {}) == "paused"
    assert apply_decision(store, waiting, {"status": "expired"}) == "final"
    assert _approval_row(store, {"checkpoint": {}}) is None
    from ar_domain.approvals.pending import hold
    from ar_domain.tools.resume import _continue_loop

    blank: dict[str, object] = {"checkpoint": {}}
    hold(blank, {"approval_id": uuid.uuid4()})
    saved = store.approvals
    store.approvals = None  # type: ignore[assignment]
    assert _approval_row(store, blank) is None
    store.approvals = saved
    opened = {"checkpoint": {"worker_loop": {"opened": True, "messages": None}}}
    assert _continue_loop(opened, "wrote") is True
    monkeypatch.setattr("ar_domain.tools.worker_loop.worker_loop_open", lambda _run: True)
    monkeypatch.setattr("ar_domain.tools.worker_loop.read_worker_loop", lambda _run: "nope")
    assert _continue_loop({}, "wrote") is False
    settle_approval(store, {"id": uuid.uuid4(), "run_id": held_id, "status": "not-a-decision"})
    _resume(store, {"checkpoint": {}}, {"id": uuid.uuid4()})


@pytest.mark.asyncio
async def test_a_queued_step_stops_on_quota_and_reports_shape() -> None:
    from ar_common.errors import QuotaExceededError
    from ar_runtime.activities.advance_chat_step import _step_body, advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    bind_store(object())
    missing = await advance_chat_step({"run_id": str(uuid.uuid4())})
    assert missing["status"] == "missing_store"
    store = demo_store()
    bind_store(store)
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hi", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    run["status"] = "queued"

    def _over(*_args: object, **_kwargs: object) -> None:
        raise QuotaExceededError(
            "over",
            quota_id="runs",
            metric="runs",
            period="month",
            limit=1,
            used=1,
            resets_at="2026-12-01T00:00:00Z",
        )

    import ar_runtime.activities.start_run as start_run

    original = start_run.assert_start
    start_run.assert_start = _over  # type: ignore[assignment]
    try:
        stopped = await advance_chat_step({"run_id": str(run["id"])})
    finally:
        start_run.assert_start = original
    assert stopped["status"] == "quota_exceeded"
    run["status"] = "completed"
    finished = await advance_chat_step({"run_id": str(run["id"])})
    assert finished["kind"] == "final"

    async def _one_step(_run_id: uuid.UUID, _text: str, _names: list[str]) -> str:
        return "final"

    store.advance_turn = _one_step  # type: ignore[method-assign]
    run["status"] = "waiting_input"
    followed = await advance_chat_step(
        {"run_id": str(run["id"]), "decision": {"status": "input", "text": "ok"}}
    )
    assert followed["kind"] == "final"
    from ar_domain.approvals.pending import hold

    held_run: dict[str, object] = {"status": "waiting_approval", "checkpoint": {}}
    hold(held_run, {"approval_id": uuid.uuid4()})
    paused = _step_body(held_run, "waiting_approval", "paused", "run", "q")
    assert "approval_id" in paused
    empty = _step_body(
        {"checkpoint": {"pending_approval": {}}},
        "waiting_approval",
        "paused",
        "run",
        "q",
    )
    assert "approval_id" not in empty
    fanned = _step_body(
        {
            "checkpoint": {
                "research": {
                    "question": "q",
                    "queries": [{"id": "1", "text": "q", "status": "pending"}],
                }
            }
        },
        "running",
        "fanout",
        "run",
        "q",
    )
    assert fanned["subtasks"]


def test_resume_without_a_worker_is_not_run_here() -> None:
    store = demo_store()
    store.temporal_client = None
    tenant, user = demo_id("tenant"), demo_id("admin")
    run_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "user_id": user,
        "status": "failed",
        "conversation_id": uuid.uuid4(),
        "checkpoint": {"worker_loop": {"opened": True}},
    }
    resumed = store.resume_run(tenant, user, run_id)
    assert resumed["status"] == "failed"
    error = store.runs[run_id].get("error")
    assert isinstance(error, dict)
    assert error["reason"] == "not_resumed"


def test_a_sync_eval_start_survives_a_duplicate_workflow() -> None:
    store = demo_store()
    connect_chat(store, demo_id("tenant"))

    class _Duplicate:
        async def start_workflow(self, *_args: object, **_kwargs: object) -> None:
            raise type("WorkflowAlreadyStartedError", (Exception,), {})("dup")

    store.temporal_client = _Duplicate()
    actor = Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
    )
    book = EvalBook(store)
    suite = book.create_suite(actor, {"name": "Sync", "kind": "functional"})
    book.create_case(
        actor,
        suite["id"],  # type: ignore[arg-type]
        {
            "name": "hello",
            "input": {"messages": ["Say hello"]},
            "assertions": [{"type": "contains", "value": "Say hello"}],
        },
    )
    box: dict[str, object] = {}

    def _start(body: dict[str, object]) -> None:
        box["row"] = book.start_run(actor, suite["id"], body)  # type: ignore[arg-type]

    import threading

    thread = threading.Thread(
        target=_start, args=({"agent_version_ref": "published"},), daemon=True
    )
    thread.start()
    thread.join()
    queued = box["row"]
    assert isinstance(queued, dict)
    assert queued["status"] == "queued"

    class _Down:
        async def start_workflow(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("frontend down")

    store.temporal_client = _Down()
    thread = threading.Thread(
        target=_start, args=({"agent_version_ref": "published"},), daemon=True
    )
    thread.start()
    thread.join()
    again = box["row"]
    assert isinstance(again, dict)
    assert store.eval_runs[uuid.UUID(str(again["id"]))]["status"] == "queued"


async def _wait(store: object) -> None:
    import asyncio

    tasks = [task for task in getattr(store, "tasks", []) if not task.done()]
    if tasks:
        await asyncio.gather(*tasks)

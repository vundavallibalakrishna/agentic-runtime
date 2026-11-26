"""A step the platform stopped is not a cancel by the person, and a worker takes no work
until the engine that masks tool results is built."""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from temporalio.activity import ActivityCancellationDetails

from ar_domain.demo_ids import demo_id
from ar_domain.tools.resume import fail_cut_off, mark_cancelled
from ar_runtime.activities import advance_chat_step as step
from ar_testing.demo import demo_store


def _details(**flags: bool) -> ActivityCancellationDetails:
    return ActivityCancellationDetails(**flags)


@pytest.mark.parametrize(
    ("flags", "reason"),
    [
        ({"cancel_requested": True}, ""),
        ({"timed_out": True}, "step_timeout"),
        ({"worker_shutdown": True}, "worker_shutdown"),
        ({}, ""),
    ],
)
def test_why_a_step_was_stopped(
    flags: dict[str, bool], reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(step.activity, "cancellation_details", lambda: _details(**flags))
    assert step._cut_off_reason() == reason


def test_outside_an_activity_there_is_no_reason() -> None:
    assert step._cut_off_reason() == ""


def _running_run() -> tuple[object, dict[str, object]]:
    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Hello", schedule=False
    )
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    run["status"] = "running"
    return store, run


def test_a_cut_off_step_fails_the_run_and_says_why() -> None:
    store, run = _running_run()
    fail_cut_off(store, run, "step_timeout")
    assert run["status"] == "failed"
    assert run["error"] == {
        "code": "upstream_timeout",
        "message": "This answer was stopped because it took too long. Please ask again.",
        "reason": "step_timeout",
    }
    kinds = [str(event["type"]) for event in store.events[run["id"]]]  # type: ignore[attr-defined]
    assert "run.cancelled" not in kinds


def test_a_stop_someone_asked_for_is_still_a_cancel() -> None:
    store, run = _running_run()
    mark_cancelled(store, run)
    assert run["status"] == "cancelled"
    last = store.events[run["id"]][-1]  # type: ignore[attr-defined]
    assert (last["type"], last["data"]) == ("run.cancelled", {"by": "user"})


def test_a_worker_waits_for_the_masking_engine_before_it_takes_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_runtime import worker

    order: list[str] = []

    async def warm() -> None:
        await asyncio.sleep(0)
        order.append("warm")

    monkeypatch.setattr("ar_domain.pii.analyzer.warm", warm)
    monkeypatch.setattr(worker, "bind_store", lambda _store: order.append("bound"))
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            env="dev",
            egress_allow_loopback=False,
            database_url="",
            model_gateway_url="",
            valkey_url="redis://unused/0",
        ),
    )
    monkeypatch.setattr(
        "ar_domain.readmodel.boot.build_product_store",
        lambda *_a, **_k: SimpleNamespace(),
    )
    monkeypatch.setattr("ar_domain.tools.gateway_client.configure_gateway", lambda *_a, **_k: None)

    asyncio.run(worker._prepare_store())

    assert order == ["warm", "bound"]

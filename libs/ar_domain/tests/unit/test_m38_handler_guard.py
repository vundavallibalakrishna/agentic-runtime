"""A failing tool handler is a failed call, and a run always ends. Task: M38-T02."""

import uuid

import pytest

from ar_common.errors import ArError, ErrorCode
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.orchestration.engine import resume_run
from ar_domain.tools.logic import raised_at
from ar_domain.tools.pipeline import ToolPipeline

PRIVATE = "card 4111 1111 1111 1111"


def _call(store: ChatService, name: str = "petstore.list_pets") -> dict[str, object]:
    version = next(row for row in store.tool_versions.values() if row["qualified_name"] == name)
    return ToolPipeline(store).execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": {},
            "model_call_id": "guard",
        }
    )


def _queued(store: ChatService) -> uuid.UUID:
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hello", schedule=False
    )
    return uuid.UUID(str(posted["run"]["id"]))


def test_a_handler_bug_is_a_failed_call_without_its_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    store = ChatService()
    assert _call(store)["status"] == "succeeded"

    def boom(*_args: object) -> dict[str, object]:
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr("ar_domain.tools.pipeline.dispatch", boom)
    result = _call(store)
    assert result["status"] == "failed"
    error = result["error"]
    assert isinstance(error, dict)
    assert error["code"] == "internal_error"
    assert PRIVATE not in str(result), "the exception text must not reach the model or the record"
    logged = capsys.readouterr()
    assert PRIVATE not in logged.out + logged.err, "the exception text must not reach the log"


def test_a_handler_that_refuses_tells_the_model_why(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object) -> dict[str, object]:
        raise ArError(ErrorCode.VALIDATION_FAILED, "path must be inside the workspace")

    monkeypatch.setattr("ar_domain.tools.pipeline.dispatch", refuse)
    result = _call(ChatService())
    assert result["status"] == "failed"
    assert result["error"] == {
        "code": "validation_failed",
        "message": "path must be inside the workspace",
    }


def _raise_private() -> None:
    raise ValueError(PRIVATE)


def test_raised_at_names_the_file_and_line_only() -> None:
    try:
        _raise_private()
    except ValueError as exc:
        where = raised_at(exc)
    assert where.startswith("test_m38_handler_guard.py:")
    assert PRIVATE not in where
    assert raised_at(ValueError("never raised")) == ""


@pytest.mark.asyncio
async def test_a_turn_that_crashes_ends_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    store = ChatService()
    run_id = _queued(store)

    async def crash(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr("ar_domain.tools.agent_loop.run_agent_loop", crash)
    await store.generate(run_id, "hello", [])

    run = store.runs[run_id]
    assert run["status"] == "failed"
    assert run["error"] == {
        "code": "internal_error",
        "message": "Something went wrong while working on this. The run was stopped.",
    }
    assert store.conversations[run["conversation_id"]]["active_run_id"] is None
    kinds = [str(event["type"]) for event in store.events[run_id]]
    assert kinds[-1] == "run.failed"
    assert PRIVATE not in str(store.events[run_id])


@pytest.mark.asyncio
async def test_a_resumed_turn_that_crashes_ends_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    store = ChatService()
    run_id = _queued(store)
    store.runs[run_id]["status"] = "running"

    async def crash(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr("ar_domain.tools.agent_loop.run_agent_loop", crash)
    await resume_run(store, run_id)
    assert store.runs[run_id]["status"] == "failed"


@pytest.mark.asyncio
async def test_an_error_outside_a_working_run_is_still_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ChatService()
    with pytest.raises(KeyError):
        await store.generate(uuid.uuid4(), "hello", [])

    run_id = _queued(store)
    store.runs[run_id]["status"] = "waiting_approval"

    async def crash(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError("late failure")

    monkeypatch.setattr("ar_domain.tools.agent_loop.run_agent_loop", crash)
    with pytest.raises(RuntimeError):
        await resume_run(store, run_id)
    assert store.runs[run_id]["status"] == "waiting_approval", "a paused run is not failed here"

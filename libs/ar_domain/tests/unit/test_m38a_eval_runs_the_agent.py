"""An eval run calls the agent, and a tool call inside it is mocked or refused. Task: M38a-T02b."""

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.evals.book import EvalBook
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_testing.stand_in import StandIn

FETCHES: list[dict[str, object]] = [
    {
        "match": {"last_tool_result": {"tool": "general__fetch"}},
        "respond": {"text": "The page says: {{last_tool_result}}"},
    },
    {
        "match": {"contains": "status page"},
        "respond": {
            "tool_calls": [
                {"name": "general__fetch", "arguments": {"url": "https://status.example/now"}}
            ]
        },
    },
]
WRITES: list[dict[str, object]] = [
    {
        "match": {"last_tool_result": {"tool": "general__http"}},
        "respond": {"text": "I could not send it."},
    },
    {
        "match": {"contains": "send"},
        "respond": {
            "tool_calls": [
                {
                    "name": "general__http",
                    "arguments": {
                        "method": "POST",
                        "url": "https://hooks.example/notify",
                        "body": {"text": "hi"},
                    },
                }
            ]
        },
    },
]


def _actor() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMISSION_KEYS,
        display_name="Admin",
    )


def _suite(
    stand_in: StandIn, script_set: str, scripts: list[dict[str, object]], case: dict[str, object]
) -> tuple[ChatService, EvalBook, uuid.UUID]:
    store = demo_store(allow_loopback=True)
    stand_in.script(script_set, scripts)
    stand_in.connect(store, demo_id("tenant"), script_set=script_set)
    book = EvalBook(store)
    suite = book.create_suite(_actor(), {"name": script_set, "kind": "functional"})
    suite_id = suite["id"]
    assert isinstance(suite_id, uuid.UUID)
    book.create_case(_actor(), suite_id, case)
    return store, book, suite_id


def _calls(store: ChatService) -> list[dict[str, object]]:
    return [row for row in store.tool_calls.values() if row.get("qualified_name")]


def test_a_case_runs_the_agent_and_a_mock_answers_its_tool_call(stand_in: StandIn) -> None:
    store, book, suite_id = _suite(
        stand_in,
        "eval-fetch",
        FETCHES,
        {
            "name": "status",
            "input": {"messages": ["What does the status page say?"]},
            "tool_mocks": [{"tool": "general.fetch", "result": {"text": "All systems normal."}}],
            "assertions": [
                {"type": "tool_called", "tool": "general.fetch"},
                {"type": "contains", "value": "All systems normal."},
                {"type": "max_steps", "value": 4},
            ],
        },
    )
    run = book.start_run(_actor(), suite_id, {"agent_version_ref": "published"})
    assert run["status"] == "completed"
    assert run["summary"]["pass_rate"] == 1  # type: ignore[index]
    calls = _calls(store)
    assert [(row["qualified_name"], row["status"]) for row in calls] == [
        ("general.fetch", "succeeded")
    ]
    eval_runs = [row for row in store.runs.values() if row.get("trigger") == "eval"]
    assert len(eval_runs) == 1
    assert eval_runs[0]["eval_context"]["tool_mocks"]  # type: ignore[index]
    conversation = store.conversations[eval_runs[0]["conversation_id"]]
    assert conversation["channel"] == "eval"


def test_a_write_in_an_eval_run_is_refused_and_never_waits_for_approval(
    stand_in: StandIn,
) -> None:
    store, book, suite_id = _suite(
        stand_in,
        "eval-write",
        WRITES,
        {
            "name": "notify",
            "input": {"messages": ["Please send the notification."]},
            "assertions": [{"type": "contains", "value": "could not send"}],
        },
    )
    run = book.start_run(_actor(), suite_id, {"agent_version_ref": "published"})
    assert run["status"] == "completed"
    assert run["summary"]["pass_rate"] == 1  # type: ignore[index]
    call = _calls(store)[0]
    assert call["qualified_name"] == "general.http"
    assert call["status"] == "failed"
    assert call["error"]["code"] == "eval_write_blocked"  # type: ignore[index]
    assert not store.approvals, "an eval run must not ask a person to approve a write"
    assert all(row["status"] == "completed" for row in store.runs.values() if row.get("trigger"))


def test_a_case_fails_when_the_model_answers_something_else(stand_in: StandIn) -> None:
    _store, book, suite_id = _suite(
        stand_in,
        "eval-wrong",
        [{"match": {}, "respond": {"text": "I do not know."}}],
        {
            "name": "capital",
            "input": {"messages": ["What is the capital of France?"]},
            "assertions": [{"type": "contains", "value": "Paris"}],
        },
    )
    run = book.start_run(_actor(), suite_id, {"agent_version_ref": "published"})
    assert run["summary"]["pass_rate"] == 0  # type: ignore[index]


@pytest.mark.asyncio
async def test_a_run_started_in_a_serving_process_is_queued_then_scored(
    stand_in: StandIn,
) -> None:
    store, book, suite_id = _suite(
        stand_in,
        "eval-queued",
        [{"match": {}, "respond": {"text": "Paris"}}],
        {
            "name": "capital",
            "input": {"messages": ["What is the capital of France?"]},
            "assertions": [{"type": "contains", "value": "Paris"}],
        },
    )
    started = book.start_run(_actor(), suite_id, {"agent_version_ref": "published"})
    assert started["status"] == "queued"
    assert started["summary"] == {}
    await asyncio.gather(*store.tasks)
    finished = store.eval_runs[started["id"]]  # type: ignore[index]
    assert finished["status"] == "completed"
    assert finished["summary"]["pass_rate"] == 1


def test_a_run_that_breaks_ends_as_failed(
    stand_in: StandIn, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, book, suite_id = _suite(
        stand_in,
        "eval-breaks",
        [{"match": {}, "respond": {"text": "Paris"}}],
        {
            "name": "x",
            "input": {"messages": ["hello"]},
            "assertions": [{"type": "contains", "value": "Paris"}],
        },
    )

    def broken(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("store is unavailable")

    monkeypatch.setattr(store, "post_message", broken)
    run = book.start_run(_actor(), suite_id, {"agent_version_ref": "published"})
    assert run["status"] == "failed"
    assert run["finished_at"] is not None

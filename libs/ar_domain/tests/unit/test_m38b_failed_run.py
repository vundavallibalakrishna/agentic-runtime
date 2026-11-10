"""A failed run is marked as one, on the run and on its reply (M38b-T10, finding F11).

Five code paths each ended a failed run by marking the reply it was making as completed,
with the reason as its text. On the screen that read as an answer from the agent. The
reply is now marked failed, the reason travels with it, and a later turn is not given it
as an answer.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.demo_ids import demo_id
from ar_domain.memory.session import prepare_prompt
from ar_domain.orchestration.reconcile import reconcile_interrupted
from ar_domain.runs.failure import fail_run, reply_error
from ar_domain.tools.agent_loop import fail_unexpected
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

TENANT = demo_id("tenant")
USER = demo_id("admin")


def _turn(
    store: ChatService, text: str = "Say hello"
) -> tuple[dict[str, object], dict[str, object]]:
    """A posted message and the run it started, with the reply the run is making."""
    conversation_id = uuid.UUID(str(store.create_conversation(TENANT, USER, None)["id"]))
    posted = store.post_message(TENANT, USER, conversation_id, text, schedule=False)
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    reply = store.messages[run["assistant_message_id"]]
    run["status"] = "running"
    reply["status"] = "streaming"
    return run, reply


def test_a_failed_run_marks_its_reply_failed_and_carries_the_reason() -> None:
    store = demo_store()
    run, reply = _turn(store)
    seen: list[tuple[str, dict[str, object]]] = []
    store._emit = lambda _run, kind, data: seen.append((kind, data))  # type: ignore[method-assign]

    fail_run(store, run, code="model_error", message="The model provider did not answer.")

    assert run["status"] == "failed"
    assert run["error"] == {"code": "model_error", "message": "The model provider did not answer."}
    assert run["ended_at"] is not None
    assert reply["status"] == "failed"
    assert reply["text"] == "The model provider did not answer."
    assert store.conversations[run["conversation_id"]]["active_run_id"] is None
    assert seen == [("run.failed", {"error": run["error"]})]


def test_what_the_reply_had_already_said_is_kept() -> None:
    store = demo_store()
    run, reply = _turn(store)
    reply["text"] = "The first two points are"
    fail_run(store, run, code="internal_error", message="The run was stopped.")
    assert reply["status"] == "failed"
    assert reply["text"] == "The first two points are"
    assert reply_error(store, reply) == {
        "code": "internal_error",
        "message": "The run was stopped.",
    }


def test_the_screen_is_given_the_reason_with_the_reply() -> None:
    store = demo_store()
    run, _reply = _turn(store)
    fail_run(store, run, code="model_error", message="The model provider did not answer.")
    shown = store.get_conversation(TENANT, USER, run["conversation_id"], read_all=False)["messages"]
    failed = next(item for item in shown if item["role"] == "assistant")
    assert failed["status"] == "failed"
    assert failed["error"] == {
        "code": "model_error",
        "message": "The model provider did not answer.",
    }
    answered = next(item for item in shown if item["role"] == "user")
    assert "error" not in answered


def test_a_failed_reply_is_not_part_of_the_next_turns_history() -> None:
    store = demo_store()
    run, _reply = _turn(store, "First question")
    fail_run(store, run, code="model_error", message="The model provider did not answer.")
    conversation = store.conversations[run["conversation_id"]]
    posted = store.post_message(TENANT, USER, conversation["id"], "Second question", schedule=False)
    second = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    version = store.versions[store.agents[conversation["agent_id"]]["published_version_id"]]
    prepare_prompt(store, second, conversation, version["definition"], "Second question")
    history = [item["content"] for item in second["prompt_messages"]]
    joined = "\n".join(history)
    assert "First question" in joined
    assert "untrusted_content" in joined
    assert not any("did not answer" in item for item in history)


def test_every_way_a_run_fails_ends_the_same_way() -> None:
    store = demo_store()

    run, reply = _turn(store)
    fail_unexpected(store, run["id"], RuntimeError("boom"))
    assert (run["status"], reply["status"], run["error"]["code"]) == (
        "failed",
        "failed",
        "internal_error",
    )

    run, reply = _turn(store)
    store._fail_context(run, store.conversations[run["conversation_id"]], reply)
    assert (run["status"], reply["status"], run["error"]["code"]) == (
        "failed",
        "failed",
        "context_length_exceeded",
    )

    run, reply = _turn(store)
    store._fail_quota(run, store.conversations[run["conversation_id"]], reply, "over")
    assert (run["status"], reply["status"], run["error"]["code"]) == (
        "failed",
        "failed",
        "quota_exceeded",
    )

    run, reply = _turn(store)
    reconcile_interrupted(store)
    assert (run["status"], reply["status"], run["error"]["code"]) == (
        "failed",
        "failed",
        "interrupted",
    )

"""Worker terminal states release conversations and remain safe to retry."""

import uuid
from unittest.mock import AsyncMock

import pytest

from ar_common.errors import QuotaExceededError
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.events.sign import public_json_bytes
from ar_runtime.activities.execute_chat_turn import execute_chat_turn, finish_chat_turn


def queued() -> tuple[ChatService, uuid.UUID]:
    store = ChatService()
    conversation = store.create_conversation(demo_id("tenant"), demo_id("admin"), None)
    posted = store.post_message(
        demo_id("tenant"),
        demo_id("admin"),
        uuid.UUID(str(conversation["id"])),
        "hello",
        schedule=False,
    )
    return store, uuid.UUID(str(posted["run"]["id"]))


@pytest.mark.parametrize("status", ["cancelled", "failed"])
async def test_finish_is_terminal_and_idempotent(
    status: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, run_id = queued()
    monkeypatch.setattr("ar_runtime.activities.execute_chat_turn.current_store", lambda: store)
    flush = AsyncMock()
    monkeypatch.setattr("ar_domain.durable.flush.flush_store", flush)
    run = store.runs[run_id]
    assistant = store.messages[run["assistant_message_id"]]
    assistant["text"] = "A partial reply"
    result = await finish_chat_turn({"run_id": str(run_id), "status": status})
    assert result["status"] == status
    assert store.conversations[run["conversation_id"]]["active_run_id"] is None
    assert assistant["text"] == "A partial reply"
    assert store.events[run_id][-1]["type"] == f"run.{status}"
    count = len(store.events[run_id])
    await finish_chat_turn({"run_id": str(run_id), "status": "failed"})
    assert len(store.events[run_id]) == count
    assert (await execute_chat_turn({"run_id": str(run_id)}))["status"] == status
    assert flush.await_count >= 2


async def test_quota_failure_emits_terminal_event_and_releases_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, run_id = queued()
    monkeypatch.setattr("ar_runtime.activities.execute_chat_turn.current_store", lambda: store)

    def deny(*args: object) -> None:
        raise QuotaExceededError(
            "Run budget exhausted",
            quota_id="test",
            metric="runs",
            period="day",
            limit=1,
            used=1,
            resets_at="2026-10-29T00:00:00Z",
        )

    monkeypatch.setattr("ar_runtime.activities.start_run.assert_start", deny)
    result = await execute_chat_turn({"run_id": str(run_id)})
    run = store.runs[run_id]
    assert result["status"] == "quota_exceeded"
    assert store.conversations[run["conversation_id"]]["active_run_id"] is None
    assert store.events[run_id][-1]["type"] == "run.failed"
    assert run["error"]["code"] == "quota_exceeded"


def test_database_uuid_subclass_can_stream_without_losing_camel_case() -> None:
    class DatabaseUUID(uuid.UUID):
        pass

    value = DatabaseUUID(str(uuid.uuid4()))
    assert public_json_bytes({"run_id": value}) == b'{"runId":"' + str(value).encode() + b'"}'
    with pytest.raises(TypeError):
        public_json_bytes({"unsupported": object()})

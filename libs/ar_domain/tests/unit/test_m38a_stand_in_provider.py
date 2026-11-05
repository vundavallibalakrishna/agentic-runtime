"""A turn reaches the stand-in as an ordinary provider and runs the real loop. Task: M38a-T01."""

import uuid

import pytest

from ar_domain.chat.service import ChatService, demo_id
from ar_testing.stand_in import MODEL, StandIn

SCRIPT_SET = "m38a-t01"
SCRIPTS: list[dict[str, object]] = [
    {
        "match": {"last_tool_result": {"tool": "general__list_files"}},
        "respond": {"text": "The workspace has no files yet."},
    },
    {
        "match": {"contains": "what files"},
        "respond": {"tool_calls": [{"name": "general__list_files", "arguments": {}}]},
    },
]


def _connected(stand_in: StandIn) -> ChatService:
    store = ChatService(allow_loopback=True)
    stand_in.script(SCRIPT_SET, SCRIPTS)
    stand_in.connect(store, demo_id("tenant"), script_set=SCRIPT_SET)
    return store


def test_the_stand_in_is_a_provider_like_any_other(stand_in: StandIn) -> None:
    store = _connected(stand_in)
    model, headers, _timeout, real = store._completion_call(demo_id("tenant"), "reasoning")
    assert model == MODEL
    assert real is True, "the product must not treat the stand-in as a fake"
    assert headers == {}, "no special header reaches the endpoint"
    provider = next(row for row in store.providers.values() if row["name"].startswith("stand-in"))
    assert provider["kind"] == "openai_compatible"
    assert str(provider["base_url"]).endswith(f"/s/{SCRIPT_SET}/v1")


@pytest.mark.asyncio
async def test_a_turn_runs_the_agent_loop_and_calls_a_tool(stand_in: StandIn) -> None:
    store = _connected(stand_in)
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    question = "what files are in the workspace?"
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), question, schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))

    await store.generate(run_id, question, [])

    run = store.runs[run_id]
    assert run["status"] == "completed", run.get("error")
    assistant = store.messages[run["assistant_message_id"]]
    assert assistant["text"] == "The workspace has no files yet."
    calls = [row for row in store.tool_calls.values() if row.get("run_id") == run_id]
    assert [(row["qualified_name"], row["status"]) for row in calls] == [
        ("general.list_files", "succeeded")
    ]
    kinds = [str(event["type"]) for event in store.events[run_id]]
    assert "tool_call.completed" in kinds
    assert kinds[-1] == "run.completed"

"""M21 agent loop: plan, act, retry, check, and approval."""

import asyncio
import uuid

from ar_domain.agents.logic import assistant_definition
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.models.logic import completion_message
from ar_domain.tools.agent_loop import run_agent_loop


def _store() -> ChatService:
    store = ChatService()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
    return store


def _script(store: ChatService, steps: list[dict[str, object]]) -> None:
    pending = list(steps)

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tools, tenant_id, model_alias
        return pending.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]


def test_assistant_can_call_tools() -> None:
    definition = assistant_definition()
    budget = definition["budget"]
    assert isinstance(budget, dict)
    assert budget["max_tool_calls"] == 8
    tools = definition["tools"]
    assert isinstance(tools, list) and tools
    assert tools[0]["server"] == "control"  # type: ignore[index]


def test_completion_message_reads_tool_calls() -> None:
    parsed = completion_message(
        {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "control__checkpoint",
                                    "arguments": '{"note": "ready"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
    )
    calls = parsed["tool_calls"]
    assert isinstance(calls, list)
    assert calls[0]["name"] == "control__checkpoint"  # type: ignore[index]
    assert calls[0]["arguments"] == {"note": "ready"}  # type: ignore[index]


def test_fake_provider_leaves_the_turn_alone() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hello", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    run = store.runs[run_id]
    assistant = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    assert asyncio.run(run_agent_loop(store, run, assistant, "hello")) is False


def test_loop_retries_a_failed_checkpoint_and_checks() -> None:
    store = _store()
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [
                    {"id": "c1", "name": "control__checkpoint", "arguments": {"note": "ready"}}
                ],
                "usage": {"tokens_in": 2, "tokens_out": 2},
                "real": True,
            },
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c2",
                        "name": "control__checkpoint",
                        "arguments": {"note": "ready", "confirm": True},
                    }
                ],
                "usage": {"tokens_in": 2, "tokens_out": 2},
                "real": True,
            },
            {
                "text": "Checkpoint saved: ready",
                "tool_calls": [],
                "usage": {"tokens_in": 2, "tokens_out": 4},
                "real": True,
            },
        ],
    )
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "Save a checkpoint",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "Save a checkpoint", []))
    run = store.runs[run_id]
    assert run["status"] == "completed"
    answer = store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"]
    assert "Checkpoint saved: ready" in str(answer)
    actions = [str(row["action"]) for row in store.audit_log]
    assert "run.planned" in actions
    assert "tool.called" in actions
    assert "run.retried" in actions
    assert "run.checked" in actions
    kinds = [str(event["type"]) for event in store.events[run_id]]
    assert "plan.updated" in kinds
    assert "tool_call.failed" in kinds
    assert "tool_call.completed" in kinds


def test_change_waits_for_approval() -> None:
    store = _store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    store.ensure_assistant(tenant, user)
    for version in store.versions.values():
        definition = version.get("definition")
        if isinstance(definition, dict) and definition.get("tools"):
            tools = definition["tools"]
            if isinstance(tools, list) and tools and isinstance(tools[0], dict):
                include = tools[0].get("include")
                if isinstance(include, list) and "checkpoint" in include:
                    include.append("propose_change")
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "control__propose_change",
                        "arguments": {"summary": "rename the folder"},
                    }
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
                "real": True,
            }
        ],
    )
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Change the folder name", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "Change the folder name", []))
    run = store.runs[run_id]
    assert run["status"] == "waiting_approval"
    assert store.approvals

"""Agents that call each other: what stays out of the conversation, handoff, and approvals."""

from __future__ import annotations

import uuid

import pytest

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.memory.session import _history
from ar_domain.orchestration.children import _end
from ar_domain.tools.agent_loop import run_agent_loop
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

_BUDGET = {
    "max_steps": 8,
    "max_tokens": 100_000,
    "max_cost_micros": 5_000_000,
    "max_wall_clock_s": 120,
    "max_tool_calls": 8,
    "max_parallel_tool_calls": 1,
}


def _store() -> ChatService:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": ("a-model", {}, 5.0, True)  # type: ignore[method-assign]
    return store


def _agent(store: ChatService, slug: str, **extra: object) -> tuple[uuid.UUID, uuid.UUID]:
    agent_id, version_id = uuid.uuid4(), uuid.uuid4()
    tenant = demo_id("tenant")
    store.agents[agent_id] = {
        "id": agent_id,
        "tenant_id": tenant,
        "slug": slug,
        "name": slug,
        "published_version_id": version_id,
        "owner_user_id": demo_id("admin"),
        "status": "published",
    }
    store.versions[version_id] = {
        "id": version_id,
        "tenant_id": tenant,
        "agent_id": agent_id,
        "state": "published",
        "definition": {
            "instructions": "Help.",
            "budget": dict(_BUDGET),
            "subagents": {"allowed": [], "max_depth": 2, "child_timeout_s": 5},
            **extra,
        },
    }
    return agent_id, version_id


def _open(
    store: ChatService, agent_id: uuid.UUID, version_id: uuid.UUID
) -> tuple[dict[str, object], dict[str, object]]:
    tenant, user = demo_id("tenant"), demo_id("admin")
    run_id, conversation_id = uuid.uuid4(), uuid.uuid4()
    message_id, assistant_id = uuid.uuid4(), uuid.uuid4()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": tenant,
        "user_id": user,
        "agent_id": agent_id,
        "active_run_id": run_id,
    }
    store.messages[message_id] = {
        "id": message_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "run_id": run_id,
        "role": "user",
        "text": "go",
        "status": "completed",
        "content": [{"type": "text", "text": "go"}],
        "created_at": "2026-11-20T00:00:00Z",
    }
    assistant: dict[str, object] = {
        "id": assistant_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "run_id": run_id,
        "role": "assistant",
        "text": "",
        "status": "streaming",
        "content": [{"type": "text", "text": ""}],
        "created_at": "2026-11-20T00:00:01Z",
    }
    store.messages[assistant_id] = assistant
    run: dict[str, object] = {
        "id": run_id,
        "tenant_id": tenant,
        "user_id": user,
        "agent_id": agent_id,
        "agent_version_id": version_id,
        "conversation_id": conversation_id,
        "assistant_message_id": assistant_id,
        "input_message_id": message_id,
        "status": "running",
        "depth": 0,
        "parent_run_id": None,
        "root_run_id": run_id,
        "trigger": "chat",
        "usage": {},
    }
    store.runs[run_id] = run
    store.events[run_id] = []
    return run, assistant


def _script(store: ChatService, handler) -> None:  # type: ignore[no-untyped-def]
    async def complete(messages, tools, *, tenant_id, model_alias):  # type: ignore[no-untyped-def]
        del tools, tenant_id, model_alias
        return handler(messages)

    store.complete_turn = complete  # type: ignore[method-assign]


def _asks_the_desk(messages: list[dict[str, object]]) -> dict[str, object]:
    """A lead that asks its specialist once, and a specialist that answers."""
    last = str(messages[-1].get("content") or "")
    if "WHAT IS THE REFERENCE" in last and messages[-1].get("role") == "user":
        return {"text": "REF-4471", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}}
    if messages[-1].get("role") == "tool":
        return {
            "text": "The reference is REF-4471.",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        }
    call = {
        "id": "c",
        "name": "agents_call",
        "arguments": {"agent": "desk", "task": "WHAT IS THE REFERENCE"},
    }
    return {"text": "", "tool_calls": [call], "usage": {"tokens_in": 1, "tokens_out": 1}}


@pytest.mark.asyncio
async def test_what_a_lead_and_a_specialist_say_stays_out_of_the_conversation() -> None:
    store = _store()
    _agent(store, "desk")
    lead, version = _agent(store, "lead", subagents={"allowed": ["desk"], "max_depth": 2})
    run, assistant = _open(store, lead, version)
    _script(store, _asks_the_desk)
    assert await run_agent_loop(store, run, assistant, "go") is True
    assert assistant["text"] == "The reference is REF-4471."
    conversation = run["conversation_id"]
    child = next(row for row in store.runs.values() if row.get("parent_run_id") == run["id"])
    theirs = [row for row in store.messages.values() if row.get("run_id") == child["id"]]
    assert {row["role"] for row in theirs} == {"user", "assistant"}
    assert {row.get("scope") for row in theirs} == {"run"}
    shown = store._visible_messages(conversation)  # type: ignore[arg-type]
    assert [row["role"] for row in shown] == ["user", "assistant"]
    assert "WHAT IS THE REFERENCE" not in str(shown)
    # The next turn's prompt is built from the person's messages and the lead's replies.
    assistant["status"] = "completed"
    history = _history(store, conversation, None, {})
    assert "WHAT IS THE REFERENCE" not in str(history)
    assert "The reference is REF-4471." in str(history)


def test_a_child_that_will_not_finish_closes_the_reply_it_started() -> None:
    store = _store()
    reply_id = uuid.uuid4()
    store.messages[reply_id] = {"id": reply_id, "status": "streaming", "text": ""}
    child: dict[str, object] = {
        "id": uuid.uuid4(),
        "status": "running",
        "assistant_message_id": reply_id,
    }
    _end(store, child, "cancelled")
    assert child["status"] == "cancelled"
    assert child["ended_at"] is not None
    assert store.messages[reply_id]["status"] == "cancelled"
    done_id = uuid.uuid4()
    store.messages[done_id] = {"id": done_id, "status": "completed", "text": "kept"}
    finished: dict[str, object] = {"id": uuid.uuid4(), "assistant_message_id": done_id}
    _end(store, finished, "failed")
    assert store.messages[done_id]["status"] == "completed"


def test_a_run_another_agent_started_is_told_apart_from_a_persons() -> None:
    store = _store()
    top, child = uuid.uuid4(), uuid.uuid4()
    store.runs[top] = {"id": top, "parent_run_id": None}
    store.runs[child] = {"id": child, "parent_run_id": top}
    pipeline = ToolPipeline(store)
    assert pipeline._called_by_an_agent({"run_id": child}) is True
    assert pipeline._called_by_an_agent({"run_id": top}) is False
    assert pipeline._called_by_an_agent({"run_id": uuid.uuid4()}) is False
    assert pipeline._called_by_an_agent({}) is False


@pytest.mark.asyncio
async def test_a_handoff_ends_the_leads_turn_when_the_run_is_carried_out_a_step_at_a_time() -> None:
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    _agent(store, "next")
    lead, version = _agent(store, "first", subagents={"allowed": ["next"], "max_depth": 2})
    run, assistant = _open(store, lead, version)
    handed = {"times": 0}

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        if "NOTE" in str(messages[-1].get("content") or ""):
            return {
                "text": "handed answer",
                "tool_calls": [],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        handed["times"] += 1
        call = {
            "id": f"h{handed['times']}",
            "name": "agents_handoff",
            "arguments": {"agent": "next", "note": "NOTE"},
        }
        return {"text": "", "tool_calls": [call], "usage": {"tokens_in": 1, "tokens_out": 1}}

    _script(store, handler)
    kinds = []
    for _ in range(6):
        step = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
        kinds.append(step["kind"])
        if step["kind"] == "final":
            break

    def handovers() -> int:
        return sum(1 for row in store.runs.values() if row.get("parent_run_id") == run["id"])

    assert kinds[-1] == "final", kinds
    assert handovers() == 1
    assert run["status"] == "completed"
    assert assistant["text"] == "handed answer"
    # Nothing is left to do: another step does not hand over again.
    again = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    assert again["kind"] == "final"
    assert handovers() == 1


@pytest.mark.asyncio
async def test_an_agent_with_no_tools_is_asked_through_the_same_loop() -> None:
    """One way to ask the model: a plain agent's answer is written, counted and kept alike."""
    store = _store()
    plain, version = _agent(store, "plain", tools=[])
    run, assistant = _open(store, plain, version)
    seen: list[list[dict[str, object]]] = []

    def answers(messages: list[dict[str, object]]) -> dict[str, object]:
        seen.append(messages)
        return {"text": "Forty-two.", "tool_calls": [], "usage": {"tokens_in": 9, "tokens_out": 2}}

    _script(store, answers)
    assert await run_agent_loop(store, run, assistant, "go") is True
    assert len(seen) == 1
    assert assistant["text"] == "Forty-two."
    assert run["status"] == "completed"
    usage = run["usage"]
    assert isinstance(usage, dict)
    assert (usage["tokens_in"], usage["tokens_out"], usage["steps"]) == (9, 2, 1)

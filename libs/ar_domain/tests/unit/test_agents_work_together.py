"""Agents that call each other: what stays out of the conversation, handoff, and approvals."""

from __future__ import annotations

import uuid

import pytest

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.memory.session import _history
from ar_domain.orchestration.children import end_child
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


async def _carry_out(run_id: object, limit: int = 12) -> list[str]:
    """Take a run to its end a step at a time, as its workflow does.

    A step that starts other agents hands back their runs. The workflow runs each as a
    workflow of its own and comes back; here each is carried out the same way, in turn.
    """
    from ar_runtime.activities.advance_chat_step import advance_chat_step

    kinds: list[str] = []
    for _ in range(limit):
        step = await advance_chat_step({"run_id": str(run_id), "text": "go"})
        kinds.append(step["kind"])
        if step["kind"] == "agents":
            ended = [(await _carry_out(child["run_id"], limit))[-1] for child in step["children"]]
            if any(kind != "final" for kind in ended):
                # A called agent is waiting for a person, so its caller's workflow waits.
                break
        if step["kind"] in {"final", "paused"}:
            break
    return kinds


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
    # Neither side's words are a message in the conversation. The lead's reply does keep
    # the call it made, as it keeps any tool call: who was called, with what, and the answer.
    assert "WHAT IS THE REFERENCE" not in [row.get("text") for row in shown]
    saved = [call for row in shown for call in row.get("tool_calls") or []]
    assert [call["presentation"]["kind"] for call in saved] == ["agents"]
    called = saved[0]["presentation"]["agents"]
    assert [(item["agent"], item["status"], item["summary"]) for item in called] == [
        ("Desk", "completed", "REF-4471")
    ]
    assert called[0]["task"] == "WHAT IS THE REFERENCE"
    assert called[0]["child_run_id"] == str(child["id"])
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
    end_child(store, child, "cancelled")
    assert child["status"] == "cancelled"
    assert child["ended_at"] is not None
    assert store.messages[reply_id]["status"] == "cancelled"
    done_id = uuid.uuid4()
    store.messages[done_id] = {"id": done_id, "status": "completed", "text": "kept"}
    finished: dict[str, object] = {"id": uuid.uuid4(), "assistant_message_id": done_id}
    end_child(store, finished, "failed")
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
    kinds = await _carry_out(run["id"])

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
async def test_what_a_called_agent_spends_counts_when_the_run_goes_a_step_at_a_time() -> None:
    """The way a worker carries out a run also charges the caller for the agents it called."""
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    _agent(store, "reader")
    lead, version = _agent(
        store,
        "lead",
        budget={**_BUDGET, "max_tokens": 100},
        subagents={"allowed": ["reader"], "max_depth": 2},
    )
    run, _assistant = _open(store, lead, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        if any("READ" in str(row.get("content") or "") for row in messages):
            # The called agent uses more than the caller's whole budget.
            return {"text": "read", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 150}}
        if not any(row.get("role") == "tool" for row in messages):
            call = {
                "id": "c",
                "name": "agents_call",
                "arguments": {"agent": "reader", "task": "READ"},
            }
            return {"text": "", "tool_calls": [call], "usage": {"tokens_in": 1, "tokens_out": 1}}
        return {"text": "done", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}}

    _script(store, handler)
    await _carry_out(run["id"])
    # The caller had 100. The agent it called used 151 of it, so the caller stops there.
    assert run["status"] == "budget_exceeded"
    assert run["usage"]["subagents"]["tokens_out"] == 150
    # The reply says what was done before the stop, and keeps the call with its answer.
    reply = store.messages[run["assistant_message_id"]]
    assert "Nothing was finished" not in reply["text"]
    assert "reader finished the work it was given" in reply["text"]
    (kept,) = reply["tool_calls"]
    assert kept["status"] == "succeeded"
    assert [(row["agent"], row["summary"]) for row in kept["presentation"]["agents"]] == [
        ("reader", "read")
    ]


def test_a_run_loaded_from_the_database_is_named_after_its_agent() -> None:
    """A run row keeps the agent's id. What the screen shows is read from the agent."""
    store = _store()
    agent, version = _agent(store, "namer")
    run, _ = _open(store, agent, version)
    child_id = uuid.uuid4()
    store.runs[child_id] = {
        "id": child_id,
        "tenant_id": run["tenant_id"],
        "agent_id": agent,
        "parent_run_id": run["id"],
        "status": "completed",
    }
    tenant = uuid.UUID(str(run["tenant_id"]))
    assert store.get_run(tenant, uuid.UUID(str(run["id"])))["agent_slug"] == "namer"
    (child,) = store.list_children(tenant, uuid.UUID(str(run["id"])))
    assert (child["agent_name"], child["agent_slug"]) == ("namer", "namer")


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


def _reply(text: str, *, used: int = 1, calls: list[dict[str, object]] | None = None):  # type: ignore[no-untyped-def]
    return {"text": text, "tool_calls": calls or [], "usage": {"tokens_in": 1, "tokens_out": used}}


def _for(messages: list[dict[str, object]], task: str) -> bool:
    """Whether this model call belongs to the agent that was given ``task``."""
    return any(
        task in str(row.get("content") or "") for row in messages if row.get("role") == "user"
    )


def _together(*agents: str) -> list[dict[str, object]]:
    calls = [{"agent": name, "task": f"TASK {name}"} for name in agents]
    return [{"id": "p", "name": "agents_parallel", "arguments": {"calls": calls}}]


def _children(store: ChatService, run: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(store.agents[row["agent_id"]]["slug"]): row
        for row in store.runs.values()
        if row.get("parent_run_id") == run["id"]
    }


def _as_loaded(row: dict[str, object]) -> None:
    """Leave a run as another worker would load it: only what the database keeps."""
    for loose in ("agent_chain", "budget_override", "agent_slug", "agent_name", "permissions"):
        row.pop(loose, None)


@pytest.mark.asyncio
async def test_a_step_that_calls_agents_starts_their_runs_and_answers_when_they_end() -> None:
    """On a worker each called agent is a run of its own, started by the caller's workflow."""
    from ar_domain.runs.request import asked
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    _agent(store, "alpha")
    _agent(store, "beta")
    lead, version = _agent(
        store,
        "lead",
        subagents={"allowed": ["alpha", "beta"], "max_depth": 2, "child_timeout_s": 7},
    )
    run, assistant = _open(store, lead, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        if _for(messages, "TASK alpha"):
            return _reply("RED", used=3)
        if _for(messages, "TASK beta"):
            return _reply("BLUE", used=4)
        if not any(row.get("role") == "tool" for row in messages):
            return _reply("", calls=_together("alpha", "beta"))
        return _reply("RED and BLUE")

    _script(store, handler)
    first = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    assert first["kind"] == "tools"
    started = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    # The step ran no agent. It created their runs and handed them to the workflow.
    assert started["kind"] == "agents"
    children = _children(store, run)
    assert {child["run_id"] for child in started["children"]} == {
        str(row["id"]) for row in children.values()
    }
    assert all(child["steps"] is True for child in started["children"])
    for row in children.values():
        assert row["status"] == "queued"
        # What the run needs is on its request, where any worker finds it.
        assert asked(row, "waits") is True
        assert asked(row, "pool")["call"] == "p"
        assert asked(row, "budget")["max_wall_clock_s"] == 7
        assert asked(row, "agent_chain")[0] == "lead"
        _as_loaded(row)
    assert run["checkpoint"]["agent_call"]["call_id"] == "p"
    for child in started["children"]:
        assert (await _carry_out(child["run_id"]))[-1] == "final"
    assert {slug: row["status"] for slug, row in children.items()} == {
        "alpha": "completed",
        "beta": "completed",
    }
    assert (await _carry_out(run["id"]))[-1] == "final"
    assert assistant["text"] == "RED and BLUE"
    assert run["status"] == "completed"
    assert run["usage"]["subagents"] == {
        "runs": 2,
        "tokens_in": 2,
        "tokens_out": 7,
        "cost_micros": 0,
    }
    assert "agent_call" not in run["checkpoint"]
    sent = [row["type"] for row in store.events[run["id"]] if row["type"].startswith("subagent")]
    assert sent == ["subagent.started"] * 2 + ["subagent.completed"] * 2
    shown = assistant["tool_calls"][0]["presentation"]["agents"]
    assert [(row["agent"], row["status"], row["summary"]) for row in shown] == [
        ("alpha", "completed", "RED"),
        ("beta", "completed", "BLUE"),
    ]
    # The conversation still belongs to the caller's run while its agents end theirs.
    assert len({row["conversation_id"] for row in children.values()}) == 1


@pytest.mark.asyncio
async def test_a_called_agent_on_a_worker_can_ask_a_person_and_its_caller_waits() -> None:
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    _agent(store, "helper", human={"enabled": True})
    lead, version = _agent(store, "lead", subagents={"allowed": ["helper"], "max_depth": 2})
    run, assistant = _open(store, lead, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        answered = any(row.get("role") == "tool" for row in messages)
        if _for(messages, "PICK"):
            if answered:
                return _reply("They chose blue.")
            question = {"id": "q", "name": "agents_ask", "arguments": {"question": "Which?"}}
            return _reply("", calls=[question])
        if not answered:
            call = {
                "id": "c",
                "name": "agents_call",
                "arguments": {"agent": "helper", "task": "PICK"},
            }
            return _reply("", calls=[call])
        return _reply("Blue it is.")

    _script(store, handler)
    kinds = await _carry_out(run["id"])
    # The called agent stopped for a person. Nothing failed, and the caller has not gone on.
    child = _children(store, run)["helper"]
    assert child["status"] == "waiting_input"
    assert store.human_questions
    assert run["status"] == "running"
    assert kinds[-1] == "agents"
    assert run["checkpoint"]["agent_call"]["call_id"] == "c"
    # The person answers. Their answer reaches the called agent's own run.
    resumed = await advance_chat_step(
        {"run_id": str(child["id"]), "decision": {"status": "input", "text": "blue"}}
    )
    if resumed["kind"] != "final":
        await _carry_out(child["id"])
    assert child["status"] == "completed"
    assert (await _carry_out(run["id"]))[-1] == "final"
    assert assistant["text"] == "Blue it is."
    shown = assistant["tool_calls"][0]["presentation"]["agents"]
    assert [(row["agent"], row["status"], row["summary"]) for row in shown] == [
        ("helper", "completed", "They chose blue.")
    ]


@pytest.mark.asyncio
async def test_agents_run_by_different_workers_still_share_one_budget() -> None:
    """The pool is read from what each run saved, so no worker needs another's memory."""
    from ar_domain.orchestration import spend
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    _agent(store, "greedy")
    _agent(store, "late")
    lead, version = _agent(
        store,
        "lead",
        budget={**_BUDGET, "max_tokens": 100},
        subagents={"allowed": ["greedy", "late"], "max_depth": 2},
    )
    run, _assistant = _open(store, lead, version)
    asked_late = {"times": 0}

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        if _for(messages, "TASK greedy"):
            return _reply("took it all", used=150)
        if _for(messages, "TASK late"):
            asked_late["times"] += 1
            return _reply("too late")
        if not any(row.get("role") == "tool" for row in messages):
            return _reply("", calls=_together("greedy", "late"))
        return _reply("done")

    _script(store, handler)
    await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    started = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    children = _children(store, run)
    assert spend._RUNNING == {}
    await _carry_out(children["greedy"]["id"])
    # The first agent used more than the call had. The second finds the pool empty
    # before it asks the model anything.
    await _carry_out(children["late"]["id"])
    assert children["late"]["status"] == "budget_exceeded"
    assert asked_late["times"] == 0
    assert len(started["children"]) == 2
    await _carry_out(run["id"])
    assert run["status"] == "budget_exceeded"


@pytest.mark.asyncio
async def test_a_called_agent_that_never_ended_is_closed_and_the_caller_goes_on() -> None:
    """A workflow that could not run a called agent leaves its run open. The caller ends it."""
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    _agent(store, "lost")
    lead, version = _agent(store, "lead", subagents={"allowed": ["lost"], "max_depth": 2})
    run, assistant = _open(store, lead, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        if not any(row.get("role") == "tool" for row in messages):
            call = {"id": "c", "name": "agents_call", "arguments": {"agent": "lost", "task": "GO"}}
            return _reply("", calls=[call])
        return _reply("carried on without it")

    _script(store, handler)
    await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    started = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    assert started["kind"] == "agents"
    # Nobody runs the called agent. The caller's next step comes back to the call.
    kinds = []
    for _ in range(4):
        step = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
        kinds.append(step["kind"])
        if step["kind"] == "final":
            break
    assert kinds[-1] == "final", kinds
    child = _children(store, run)["lost"]
    assert child["status"] == "failed"
    assert child["error"]["code"] == "child_not_finished"
    assert str(assistant["text"]).startswith("carried on without it")
    assert len(_children(store, run)) == 1


@pytest.mark.asyncio
async def test_a_step_hands_the_workflow_every_called_agent_and_how_many_run_at_once() -> None:
    """On a worker the extra agents are not dropped: the workflow starts them in turn."""
    from ar_domain.runs.request import asked
    from ar_runtime.activities.advance_chat_step import advance_chat_step
    from ar_runtime.activities.expire_approval import bind_store

    store = _store()
    bind_store(store)
    shape = {
        "type": "object",
        "properties": {"colour": {"type": "string"}},
        "required": ["colour"],
    }
    _agent(store, "painter", contract={"description": "Names a colour.", "output_schema": shape})
    lead, version = _agent(
        store,
        "lead",
        subagents={"allowed": ["painter"], "max_depth": 2, "max_parallel": 2, "max_calls": 3},
    )
    run, assistant = _open(store, lead, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        if _for(messages, "TASK painter"):
            return _reply('{"colour": "teal"}')
        if not any(row.get("role") == "tool" for row in messages):
            return _reply("", calls=_together(*["painter"] * 4))
        return _reply("Teal, three times.")

    _script(store, handler)
    await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    started = await advance_chat_step({"run_id": str(run["id"]), "text": "go"})
    assert started["kind"] == "agents"
    assert (len(started["children"]), started["parallel"]) == (3, 2)
    children = [row for row in store.runs.values() if row.get("parent_run_id") == run["id"]]
    # What the painter promised to return is on each run, where its worker reads it.
    assert [asked(row, "response_format") for row in children] == [shape] * 3
    for child in started["children"]:
        await _carry_out(child["run_id"])
    await _carry_out(run["id"])
    shown = assistant["tool_calls"][0]["presentation"]["agents"]
    assert [row["status"] for row in shown] == ["completed"] * 3 + ["failed"]
    assert [row["summary"] for row in shown[:3]] == ['{"colour":"teal"}'] * 3
    assert "at most 3 agents" in shown[3]["summary"]

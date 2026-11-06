"""Orchestration: child runs, budgets, human steps, schedules and durable rows."""

import asyncio
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.time import utcnow
from ar_domain.demo_ids import demo_id
from ar_domain.durable.m28 import load_runtime_rows, save_runtime_rows
from ar_domain.orchestration.ask import (
    accept_human_answer,
    ask_person,
    list_questions,
    question_for_actor,
)
from ar_domain.orchestration.reconcile import reconcile_interrupted
from ar_domain.orchestration.spec import contract_line, is_cycle, subagent_spec
from ar_domain.orchestration.tables import HumanQuestion
from ar_domain.orchestration.triggers import fire_schedule
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.signature import header_for
from ar_domain.tools.agent_loop import run_agent_loop
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_BUDGET = {
    "max_steps": 6,
    "max_tokens": 8000,
    "max_cost_micros": 1000,
    "max_wall_clock_s": 30,
    "max_tool_calls": 4,
}


def _store() -> ChatService:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)  # type: ignore[method-assign]
    return store


def _agent(
    store: ChatService, slug: str, definition: dict[str, object]
) -> tuple[uuid.UUID, uuid.UUID]:
    tenant = demo_id("tenant")
    user = demo_id("admin")
    agent_id = uuid.uuid4()
    version_id = uuid.uuid4()
    store.agents[agent_id] = {
        "id": agent_id,
        "tenant_id": tenant,
        "slug": slug,
        "name": slug,
        "description": f"{slug} answers",
        "published_version_id": version_id,
        "owner_user_id": user,
        "status": "published",
    }
    store.versions[version_id] = {
        "id": version_id,
        "tenant_id": tenant,
        "agent_id": agent_id,
        "definition": definition,
        "state": "published",
    }
    return agent_id, version_id


def _definition(**extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "instructions": "Help.",
        "budget": dict(_BUDGET),
        "subagents": {"allowed": [], "max_depth": 2, "max_parallel": 4, "child_timeout_s": 5},
        "human": {"enabled": False},
        "contract": {
            "description": "A specialist.",
            "input_schema": {"task": "string"},
            "output_schema": {"answer": "string"},
        },
    }
    body.update(extra)
    return body


def _open(
    store: ChatService, agent_id: uuid.UUID, version_id: uuid.UUID
) -> tuple[dict[str, object], dict[str, object]]:
    tenant = demo_id("tenant")
    user = demo_id("admin")
    run_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    message_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
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
        "role": "user",
        "text": "go",
        "content": [{"type": "text", "text": "go"}],
    }
    assistant = {
        "id": assistant_id,
        "tenant_id": tenant,
        "conversation_id": conversation_id,
        "role": "assistant",
        "text": "",
        "status": "streaming",
        "content": [{"type": "text", "text": ""}],
    }
    store.messages[assistant_id] = assistant
    run = {
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


async def test_parallel_children_return_both_answers() -> None:
    from ar_domain.durable.tracking import install_tracking

    store = _store()
    install_tracking(store)
    _agent(store, "alpha", _definition())
    _agent(store, "beta", _definition())
    parent, version = _agent(
        store,
        "lead",
        _definition(subagents={"allowed": ["alpha", "beta"], "max_depth": 2, "max_parallel": 2}),
    )
    run, assistant = _open(store, parent, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        content = str(messages[-1].get("content") or "")
        if "ALPHA" in content:
            return {"text": "RED", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 2}}
        if "BETA" in content:
            return {"text": "BLUE", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 2}}
        if not any(item.get("role") == "tool" for item in messages):
            return {
                "text": "",
                "tool_calls": [
                    {
                        "id": "p",
                        "name": "agents_parallel",
                        "arguments": {
                            "calls": [
                                {"agent": "alpha", "task": "Say ALPHA"},
                                {"agent": "beta", "task": "Say BETA"},
                                {"agent": "alpha", "task": "extra"},
                            ]
                        },
                    }
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        return {
            "text": "RED and BLUE",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 3},
        }

    _script(store, handler)
    assert await run_agent_loop(store, run, assistant, "combine") is True
    assert run["status"] == "completed"
    assert "RED and BLUE" in str(assistant["text"])
    children = [row for row in store.runs.values() if row.get("parent_run_id") == run["id"]]
    assert len(children) == 2
    assert {row["agent_slug"] for row in children} == {"alpha", "beta"}
    assert {row["status"] for row in children} == {"completed"}
    assert run["usage"]["cost_micros"] >= 1


async def test_failed_child_lets_the_parent_recover() -> None:
    store = _store()
    _agent(store, "breaker", _definition())
    parent, version = _agent(
        store, "rescue", _definition(subagents={"allowed": ["breaker"], "max_depth": 2})
    )
    run, assistant = _open(store, parent, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        content = str(messages[-1].get("content") or "")
        if "BREAK" in content:
            return {"text": "The model provider returned an error.", "tool_calls": [], "usage": {}}
        if not any(item.get("role") == "tool" for item in messages):
            return {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c",
                        "name": "agents_call",
                        "arguments": {"agent": "breaker", "task": "BREAK"},
                    }
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        return {
            "text": "RECOVERED after the child failed",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        }

    _script(store, handler)
    assert await run_agent_loop(store, run, assistant, "go") is True
    assert "RECOVERED" in str(assistant["text"])
    child = next(row for row in store.runs.values() if row.get("parent_run_id") == run["id"])
    assert child["status"] == "failed"


async def test_depth_stops_a_recursive_self_call() -> None:
    store = _store()
    parent, version = _agent(
        store,
        "loop",
        _definition(
            subagents={
                "allowed": [],
                "allow_self_clone": True,
                "max_depth": 1,
                "max_parallel": 1,
                "child_timeout_s": 5,
            },
            budget={**_BUDGET, "max_tool_calls": 2, "max_cost_micros": 2},
        ),
    )
    run, assistant = _open(store, parent, version)
    calls = {"n": 0}

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        calls["n"] += 1
        if any(item.get("role") == "tool" for item in messages):
            return {"text": "stopped", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}}
        return {
            "text": "",
            "tool_calls": [
                {"id": "s", "name": "agents_call", "arguments": {"agent": "loop", "task": "again"}}
            ],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        }

    _script(store, handler)
    assert await run_agent_loop(store, run, assistant, "again") is True
    assert calls["n"] < 12
    assert run["status"] in {"completed", "budget_exceeded"}


async def test_child_timeout_is_not_retried() -> None:
    store = _store()
    _agent(store, "slow", _definition())
    parent, version = _agent(
        store,
        "timer",
        _definition(subagents={"allowed": ["slow"], "max_depth": 2, "child_timeout_s": 1}),
    )
    run, assistant = _open(store, parent, version)

    async def complete(messages, tools, *, tenant_id, model_alias):  # type: ignore[no-untyped-def]
        del tools, tenant_id, model_alias
        content = str(messages[-1].get("content") or "")
        if "WAIT" in content:
            await asyncio.sleep(2)
            return {"text": "late", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}}
        if not any(item.get("role") == "tool" for item in messages):
            return {
                "text": "",
                "tool_calls": [
                    {
                        "id": "t",
                        "name": "agents_call",
                        "arguments": {"agent": "slow", "task": "WAIT"},
                    }
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        return {
            "text": "RECOVERED after the child failed",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    assert await run_agent_loop(store, run, assistant, "go") is True
    assert "RECOVERED" in str(assistant["text"])
    child = next(row for row in store.runs.values() if row.get("parent_run_id") == run["id"])
    assert child["error"]["code"] == "child_timeout"


async def test_human_question_resumes_and_blocks_self_approval() -> None:
    store = _store()
    parent, version = _agent(store, "asker", _definition(human={"enabled": True}))
    run, assistant = _open(store, parent, version)
    phase = {"n": 0}

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        phase["n"] += 1
        if any(item.get("role") == "tool" for item in messages):
            return {
                "text": "the answer is blue",
                "tool_calls": [],
                "usage": {"tokens_in": 1, "tokens_out": 2},
            }
        if phase["n"] == 1:
            return {
                "text": "",
                "tool_calls": [
                    {
                        "id": "q",
                        "name": "agents_ask",
                        "arguments": {"question": "Which colour?", "options": ["blue", "red"]},
                    }
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        return {"text": "done", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 1}}

    _script(store, handler)
    assert await run_agent_loop(store, run, assistant, "ask") is True
    assert run["status"] == "waiting_input"
    assert store.human_questions
    other = uuid.uuid4()
    try:
        accept_human_answer(store, demo_id("tenant"), other, run, "blue")
        raised = False
    except NotFoundError:
        raised = True
    assert raised
    try:
        store.submit_input(demo_id("tenant"), demo_id("admin"), run["id"], "green")
        rejected = False
    except ValidationFailedError:
        rejected = True
    assert rejected
    assert run["status"] == "waiting_input"
    store.submit_input(demo_id("tenant"), demo_id("admin"), run["id"], "blue")
    if store.tasks:
        await asyncio.gather(*store.tasks)
    assert run["status"] == "completed"
    assert "blue" in str(assistant["text"])
    question = next(iter(store.human_questions.values()))
    assert question["answer"] == "blue"
    assert question["status"] == "answered"

    approval = ask_person(
        store,
        run,
        assistant,
        {"question": "Approve?", "kind": "approval"},
        "a",
    )
    assert approval is not None and approval["failed"] is True
    run["status"] = "waiting_input"
    run["pending_question_id"] = next(iter(store.human_questions))
    row = store.human_questions[run["pending_question_id"]]
    row["kind"] = "approval"
    row["status"] = "pending"
    row["assignee_user_id"] = demo_id("approver")
    row["requested_by_user_id"] = demo_id("approver")
    try:
        accept_human_answer(store, demo_id("tenant"), demo_id("approver"), run, "yes")
        blocked = False
    except ValidationFailedError:
        blocked = True
    assert blocked


async def test_handoff_uses_the_child_answer() -> None:
    store = _store()
    _agent(store, "next", _definition())
    parent, version = _agent(
        store, "first", _definition(subagents={"allowed": ["next"], "max_depth": 2})
    )
    run, assistant = _open(store, parent, version)

    def handler(messages: list[dict[str, object]]) -> dict[str, object]:
        content = str(messages[-1].get("content") or "")
        if "NOTE" in content:
            return {
                "text": "handed answer",
                "tool_calls": [],
                "usage": {"tokens_in": 1, "tokens_out": 2},
            }
        return {
            "text": "",
            "tool_calls": [
                {
                    "id": "h",
                    "name": "agents_handoff",
                    "arguments": {"agent": "next", "note": "NOTE"},
                }
            ],
            "usage": {"tokens_in": 1, "tokens_out": 1},
        }

    _script(store, handler)
    assert await run_agent_loop(store, run, assistant, "go") is True
    assert assistant["text"] == "handed answer"
    assert run["status"] == "completed"


async def test_schedule_skips_and_queues() -> None:
    store = _store()
    agent = next(row["id"] for row in store.agents.values() if row.get("slug") == "assistant")
    routine_id = uuid.uuid4()
    store.routines[routine_id] = {
        "id": routine_id,
        "tenant_id": demo_id("tenant"),
        "owner_user_id": demo_id("admin"),
        "agent_id": agent,
        "name": "Morning",
        "instructions": "Say hello",
        "status": "active",
        "trigger_type": "schedule",
        "trigger_config": {"cron": "0 9 * * 1", "timezone": "UTC", "execute_model": False},
        "concurrency_policy": "skip",
        "delivery": [{"type": "conversation"}],
        "budget": _BUDGET,
        "max_runs_per_day": 10,
    }
    store.runs[uuid.uuid4()] = {
        "id": uuid.uuid4(),
        "routine_id": routine_id,
        "status": "running",
        "tenant_id": demo_id("tenant"),
    }
    skipped = await fire_schedule(store, routine_id, force=True)
    assert skipped["status"] == "skipped_concurrency"
    assert "still going" in str(skipped["message"])
    store.routines[routine_id]["concurrency_policy"] = "queue"
    queued = await fire_schedule(store, routine_id, force=True)
    assert queued["status"] == "queued"
    again = await fire_schedule(store, routine_id, force=True)
    assert again["status"] == "skipped_concurrency"
    for run in list(store.runs.values()):
        if run.get("routine_id") == routine_id:
            run["status"] = "completed"
    started = await fire_schedule(store, routine_id, force=True)
    assert started["status"] == "completed"
    assert started["run_id"]


def test_webhook_duplicate_does_not_start_a_second_run() -> None:
    store = _store()
    agent = next(row["id"] for row in store.agents.values() if row.get("slug") == "assistant")
    from ar_domain.agents.access import Actor
    from ar_domain.identity.permissions import PERMISSION_KEYS

    actor = Actor(
        demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, roles=frozenset({"tenant_admin"})
    )
    created = RoutineBook(store).create(
        actor,
        {
            "name": "Hook",
            "agent_id": agent,
            "instructions": "Read the payload",
            "trigger": {"type": "webhook", "execute_model": False},
            "delivery": [{"type": "conversation"}],
        },
    )
    secret = str(created["webhook"]["webhook_secret"])
    token = str(created["webhook"]["webhook_url"]).rsplit("/", 1)[-1]
    body = b'{"n":1}'
    header = header_for(secret, body, int(utcnow().timestamp()))
    book = RoutineBook(store)
    first = book.accept_webhook(token, body, header)
    second = None
    try:
        book.accept_webhook(token, body, header)
    except Exception as exc:  # noqa: BLE001
        second = exc
    assert first["status"] == "accepted"
    assert second is not None
    runs = [row for row in store.runs.values() if row.get("trigger") == "routine"]
    assert len(runs) == 1


def test_reconcile_fails_running_and_keeps_a_question() -> None:
    store = _store()
    agent, version = _agent(store, "pause", _definition(human={"enabled": True}))
    running, _assistant = _open(store, agent, version)
    waiting, assistant = _open(store, agent, version)
    waiting["status"] = "waiting_input"
    ask_person(store, waiting, assistant, {"question": "Ready?", "options": ["yes"]}, "q")
    changed = reconcile_interrupted(store)
    assert str(running["id"]) in changed
    assert running["status"] == "failed"
    assert running["error"]["code"] == "interrupted"
    assert waiting["status"] == "waiting_input"
    assert subagent_spec({"subagents": {}})["child_timeout_s"] == 45
    assert is_cycle({"agent_chain": ["a", "b"]}, "a", allow_self=True) is True
    assert is_cycle({"agent_chain": ["a"]}, "a", allow_self=True) is False


async def test_durable_rows_round_trip_in_memory() -> None:
    store = _store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    agent, version = _agent(store, "durable", _definition())
    run, _assistant = _open(store, agent, version)
    call_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    version_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    question_id = uuid.uuid4()
    sandbox_id = uuid.uuid4()
    template_id = uuid.uuid4()
    now = utcnow()
    store.tool_calls[call_id] = {
        "id": call_id,
        "tenant_id": tenant,
        "run_id": run["id"],
        "tool_id": None,
        "tool_version_id": None,
        "qualified_name": "agents_call",
        "model_call_id": "m",
        "arguments_redacted": {},
        "args_hash": "abc",
        "risk_class": "R0",
        "policy_decision": "allow",
        "status": "succeeded",
        "idempotency_key": f"{run['id']}:m",
        "result_preview": "ok",
        "is_error": False,
        "error": None,
        "latency_ms": 3,
        "approval_id": approval_id,
        "created_at": now,
    }
    store.approvals[approval_id] = {
        "id": approval_id,
        "tenant_id": tenant,
        "tool_call_id": call_id,
        "run_id": run["id"],
        "requested_for_user_id": user,
        "agent_id": agent,
        "qualified_name": "agents_call",
        "risk_class": "W2",
        "status": "pending",
        "args_hash": "abc",
        "arguments": {},
        "preview": {},
        "justification": "",
        "approver_rule": {"mode": "users", "users": [str(demo_id("approver"))]},
        "required_approvals": 1,
        "step_up_required": False,
        "expires_at": now + timedelta(hours=1),
        "created_at": now,
        "updated_at": now,
    }
    store.approval_decisions[decision_id] = {
        "id": decision_id,
        "tenant_id": tenant,
        "approval_id": approval_id,
        "approver_user_id": demo_id("approver"),
        "decision": "approve",
        "args_hash": "abc",
        "comment": "",
        "step_up_verified": False,
        "channel": "web",
        "created_at": now,
    }
    store.policies[policy_id] = {
        "id": policy_id,
        "tenant_id": tenant,
        "name": "m28",
        "description": "",
        "kind": "rules",
        "status": "active",
        "priority": 10,
        "active_version_id": version_id,
        "created_by": user,
        "created_at": now,
        "updated_at": now,
    }
    store.policy_versions[version_id] = {
        "id": version_id,
        "tenant_id": tenant,
        "policy_id": policy_id,
        "version": 1,
        "document": {"rules": []},
        "rego": None,
        "hash": "h",
        "created_by": user,
        "created_at": now,
    }
    store.sandbox_templates[template_id] = {
        "id": template_id,
        "tenant_id": None,
        "slug": "default",
        "name": "Default",
        "image_ref": "local",
        "runtime_class": "gvisor",
        "allow_browser": False,
        "allow_packages": False,
        "egress_allowlist": [],
        "max_classification": "confidential",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    store.sandboxes[sandbox_id] = {
        "id": sandbox_id,
        "tenant_id": tenant,
        "template_id": template_id,
        "scope": "conversation",
        "scope_key": "conv:1",
        "conversation_id": run["conversation_id"],
        "agent_id": agent,
        "user_id": user,
        "status": "ready",
        "driver": "docker",
        "driver_ref": "local",
        "workspace_volume": f"sandbox:{sandbox_id}",
        "cpu_seconds": 0,
        "last_active_at": now,
        "created_at": now,
        "updated_at": now,
    }
    store.human_questions[question_id] = {
        "id": question_id,
        "tenant_id": tenant,
        "run_id": run["id"],
        "requested_by_user_id": user,
        "assignee_user_id": user,
        "kind": "question",
        "question": "Ready?",
        "options": ["yes"],
        "answer": None,
        "status": "pending",
        "call_id": "q",
        "created_at": now,
        "updated_at": now,
    }

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def mappings(self) -> list[dict[str, object]]:
            return self._rows

        def first(self) -> dict[str, object] | None:
            return self._rows[0] if self._rows else None

    class Session:
        def __init__(self) -> None:
            self.calls: list[object] = []

        async def execute(self, statement: object, params: object = None) -> Result:
            self.calls.append(params)
            sql = str(statement)
            if "FROM runs" in sql:
                return Result([{"id": run["id"]}])
            if "FROM tool_calls" in sql:
                return Result([dict(store.tool_calls[call_id])])
            if "FROM human_questions" in sql:
                return Result([dict(store.human_questions[question_id])])
            if "sandbox_templates" in sql:
                return Result([dict(store.sandbox_templates[template_id])])
            return Result([])

    session = Session()
    pending = {
        "tool_calls": [dict(store.tool_calls[call_id])],
        "approvals": [dict(store.approvals[approval_id])],
        "approval_decisions": [dict(store.approval_decisions[decision_id])],
        "policies": [dict(store.policies[policy_id])],
        "policy_versions": [dict(store.policy_versions[version_id])],
        "sandboxes": [dict(store.sandboxes[sandbox_id])],
        "human_questions": [dict(store.human_questions[question_id])],
    }
    await save_runtime_rows(session, store, pending)
    assert session.calls
    fresh = demo_store()
    await load_runtime_rows(session, fresh, tenant)
    assert call_id in fresh.tool_calls
    assert question_id in fresh.human_questions
    assert template_id in fresh.sandbox_templates
    # Skip rows that cannot satisfy a foreign key.
    await save_runtime_rows(
        session,
        store,
        {
            "tool_calls": [{"id": "nope"}],
            "approvals": [{"id": approval_id}],
            "approval_decisions": [{"id": decision_id, "decision": "maybe"}],
            "policies": [],
            "policy_versions": [{"id": version_id, "document": None, "rego": "package x"}],
            "sandboxes": [{"id": sandbox_id}],
            "human_questions": [{"id": question_id, "kind": "approval", "status": "nope"}],
        },
    )


async def test_approval_link_skips_a_missing_approval() -> None:
    from ar_domain.durable.m28 import save_approval_links

    class Result:
        def first(self) -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.sql: list[str] = []

        async def execute(self, statement: object, params: object = None) -> Result:
            del params
            self.sql.append(str(statement))
            return Result()

    session = Session()
    await save_approval_links(
        session,
        [{"id": uuid.uuid4(), "approval_id": uuid.uuid4()}],
    )
    assert len(session.sql) == 1
    assert "FROM approvals" in session.sql[0]


async def test_tool_call_without_a_run_is_not_inserted() -> None:
    from ar_domain.durable.m28 import save_tool_calls

    class Result:
        def first(self) -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.sql: list[str] = []

        async def execute(self, statement: object, params: object = None) -> Result:
            del params
            self.sql.append(str(statement))
            return Result()

    session = Session()
    await save_tool_calls(
        session,
        [
            {
                "id": uuid.uuid4(),
                "tenant_id": demo_id("tenant"),
                "run_id": uuid.uuid4(),
                "qualified_name": "general.code",
            }
        ],
    )
    assert len(session.sql) == 1
    assert "FROM runs" in session.sql[0]
    assert "INSERT" not in session.sql[0]


def test_human_question_table_is_mapped() -> None:
    assert HumanQuestion.__tablename__ == "human_questions"


async def test_schedule_reports_missing_paused_and_early() -> None:
    store = _store()
    missing = await fire_schedule(store, uuid.uuid4(), force=True)
    assert missing["status"] == "missing"
    routine_id = uuid.uuid4()
    store.routines[routine_id] = {
        "id": str(routine_id),
        "tenant_id": demo_id("tenant"),
        "status": "paused",
        "next_run_at": utcnow() + timedelta(hours=2),
    }
    paused = await fire_schedule(store, routine_id)
    assert paused["status"] == "paused"
    store.routines[routine_id]["status"] = "active"
    early = await fire_schedule(store, routine_id)
    assert early["status"] == "not_due"
    store.routines[routine_id]["next_run_at"] = "later"
    assert (await fire_schedule(store, routine_id))["status"] == "not_due"


def test_inbox_lists_the_assignee_and_rejects_a_bad_answer() -> None:
    store = _store()
    store.notifications = []
    agent, version = _agent(store, "clerk", _definition(human={"enabled": True}))
    run, assistant = _open(store, agent, version)
    run["user_id"] = demo_id("admin")
    blank = ask_person(store, run, assistant, {"question": "  "}, "blank")
    assert blank is not None and blank["failed"] is True
    other = ask_person(store, run, assistant, {"question": "Pick", "kind": "other"}, "kind")
    assert other is not None and other["failed"] is True
    paused = ask_person(
        store,
        run,
        assistant,
        {
            "question": "Which?",
            "options": ["red", " "],
            "assignee_user_id": str(demo_id("admin")),
        },
        "ask",
    )
    assert paused is None
    assert store.notifications
    rows = list_questions(store, demo_id("tenant"), demo_id("admin"))
    assert rows and rows[0]["question"] == "Which?"
    assert contract_line(store, demo_id("tenant"), "missing-agent") == "missing-agent"
    question_id = rows[0]["id"]
    assert isinstance(question_id, uuid.UUID)
    wrong = None
    try:
        question_for_actor(store, demo_id("tenant"), uuid.uuid4(), question_id)
    except NotFoundError as exc:
        wrong = exc
    assert wrong is not None
    bad_answer = None
    try:
        accept_human_answer(store, demo_id("tenant"), demo_id("admin"), run, "green")
    except ValidationFailedError as exc:
        bad_answer = exc
    assert bad_answer is not None
    run["pending_question_id"] = None
    empty = ask_person(store, run, assistant, {"question": "Anything?"}, "open")
    assert empty is None
    blank_answer = None
    try:
        accept_human_answer(store, demo_id("tenant"), demo_id("admin"), run, "  ")
    except ValidationFailedError as exc:
        blank_answer = exc
    assert blank_answer is not None

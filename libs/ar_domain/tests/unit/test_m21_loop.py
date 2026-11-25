"""M21 agent loop: plan, act, retry, check, and approval."""

import asyncio
import uuid
from typing import TYPE_CHECKING

from ar_domain.agents.logic import assistant_definition
from ar_domain.demo_ids import demo_id
from ar_domain.models.logic import completion_message
from ar_domain.tools.agent_loop import run_agent_loop
from ar_testing.approval_tool import BINDING as APPROVAL_BINDING
from ar_testing.approval_tool import ENDPOINT as APPROVAL_ENDPOINT
from ar_testing.demo import demo_store
from ar_testing.retry_tool import ENDPOINT, MODEL_NAME, TOOL, offer_retry_tool

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def _store() -> ChatService:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
    offer_retry_tool(store, demo_id("tenant"))
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


def test_builtin_handlers_cover_control_memory_and_skills() -> None:
    from ar_domain.tools.handlers import dispatch

    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    offer_retry_tool(store, tenant)
    assert dispatch(store, ENDPOINT, TOOL, {}, "")["is_error"] is True
    failed = dispatch(store, ENDPOINT, TOOL, {"note": "x"}, "")
    assert failed["code"] == "upstream_error"
    unconfirmed = dispatch(store, ENDPOINT, TOOL, {"note": "x", "confirm": False}, "")
    assert unconfirmed["code"] == "validation_failed"
    assert dispatch(store, ENDPOINT, TOOL, {"note": "x", "confirm": True}, "")["is_error"] is False
    assert dispatch(store, ENDPOINT, "nope", {}, "")["code"] == "unknown_tool"
    assert dispatch(store, APPROVAL_ENDPOINT, "propose_change", {}, "")["is_error"] is True
    conversation = store.create_conversation(tenant, user, None)
    saved = dispatch(
        store,
        APPROVAL_ENDPOINT,
        "propose_change",
        {"summary": "rename", "_conversation_id": uuid.UUID(str(conversation["id"]))},
        "",
    )
    assert saved["text"] == "Change saved."
    assert dispatch(store, "builtin://memory", "search", {}, "")["is_error"] is True
    found = dispatch(
        store,
        "builtin://memory",
        "search",
        {"_tenant_id": tenant, "_user_id": user, "query": "hello"},
        "",
    )
    assert found["is_error"] is False
    saved_memory = dispatch(
        store,
        "builtin://memory",
        "save",
        {"_tenant_id": tenant, "_user_id": user, "content": "I like short answers"},
        "",
    )
    assert saved_memory["is_error"] is False
    forgotten = dispatch(
        store,
        "builtin://memory",
        "forget",
        {"_tenant_id": tenant, "_user_id": user, "query": "short answers"},
        "",
    )
    assert forgotten["is_error"] is False
    assert dispatch(
        store, "builtin://memory", "nope", {"_tenant_id": tenant, "_user_id": user}, ""
    )["is_error"]
    assert dispatch(store, "builtin://skills", "nope", {}, "")["is_error"] is True
    assert dispatch(store, "builtin://skills", "load", {"_run_id": "not-a-uuid"}, "")["is_error"]


def test_assistant_can_call_tools() -> None:
    definition = assistant_definition()
    budget = definition["budget"]
    assert isinstance(budget, dict)
    assert budget["max_tool_calls"] == 16
    tools = definition["tools"]
    assert isinstance(tools, list) and tools
    assert tools[0]["server"] == "session"  # type: ignore[index]


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
                                    "name": "session__search",
                                    "arguments": '{"query": "ready"}',
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
    assert calls[0]["name"] == "session__search"  # type: ignore[index]
    assert calls[0]["arguments"] == {"query": "ready"}  # type: ignore[index]


def test_fake_provider_leaves_the_turn_alone() -> None:
    store = demo_store()
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


def test_loop_retries_a_tool_that_fails_once_and_checks() -> None:
    store = _store()
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [{"id": "c1", "name": MODEL_NAME, "arguments": {"note": "ready"}}],
                "usage": {"tokens_in": 2, "tokens_out": 2},
                "real": True,
            },
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c2",
                        "name": MODEL_NAME,
                        "arguments": {"note": "ready", "confirm": True},
                    }
                ],
                "usage": {"tokens_in": 2, "tokens_out": 2},
                "real": True,
            },
            {
                "text": "Note saved: ready",
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
        "Save a note",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "Save a note", []))
    run = store.runs[run_id]
    assert run["status"] == "completed"
    answer = store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"]
    assert "Note saved: ready" in str(answer)
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
                if isinstance(include, list) and "search" in include:
                    tools.append(dict(APPROVAL_BINDING))
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "name": "proposals__propose_change",
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


def _run(store: ChatService, text: str) -> dict[str, object]:
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), text, schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, text, []))
    return store.runs[run_id]


def test_loop_stops_at_the_step_limit() -> None:
    store = _store()
    for version in store.versions.values():
        definition = version.get("definition")
        budget = definition.get("budget") if isinstance(definition, dict) else None
        if isinstance(budget, dict) and budget.get("max_tool_calls") == 16:
            budget["max_steps"] = 1
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [
                    {"id": "c1", "name": "session__plan_update", "arguments": {"plan": ["one"]}}
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        ],
    )
    run = _run(store, "Plan one step")
    assert run["status"] == "budget_exceeded"
    assert any(row["action"] == "run.budget_exceeded" for row in store.audit_log)


def test_unknown_tool_is_reported_and_checked() -> None:
    store = _store()
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [{"id": "c1", "name": "missing__tool", "arguments": {}}],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            },
            {
                "text": "I could not use that tool.",
                "tool_calls": [],
                "usage": {"tokens_in": 1, "tokens_out": 2},
            },
        ],
    )
    run = _run(store, "Use a missing tool")
    assert run["status"] == "completed"
    text = str(store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"])
    assert "could not" in text


def test_a_refusal_the_answer_already_explains_gets_no_extra_notice() -> None:
    """The suffix is not piled onto an answer that already says the tool was blocked (F59).

    The live case: a fetch refused by the egress rules, which the model reported as
    "blocked" — a word the old check did not know, so the notice was wrongly added.
    """
    store = _store()
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [{"id": "c1", "name": "missing__tool", "arguments": {}}],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            },
            {
                # Phrased without any of the old words ("fail", "could not", ...).
                "text": "I was blocked from reaching that host, so there is no result to share.",
                "tool_calls": [],
                "usage": {"tokens_in": 1, "tokens_out": 2},
            },
        ],
    )
    run = _run(store, "Fetch a blocked host")
    assert run["status"] == "completed"
    text = str(store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"])
    assert "A tool call failed and was not recovered." not in text
    assert "blocked" in text


def test_silent_provider_fails_the_run() -> None:
    store = _store()

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object] | None:
        del messages, tools, tenant_id, model_alias
        return None

    store.complete_turn = complete  # type: ignore[method-assign]
    run = _run(store, "Hello")
    assert run["status"] == "failed"


def test_blank_model_text_is_replaced() -> None:
    store = _store()
    _script(
        store,
        [
            {"text": "   ", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 0}},
            {"text": "   ", "tool_calls": [], "usage": {"tokens_in": 1, "tokens_out": 0}},
        ],
    )
    run = _run(store, "Say nothing")
    text = str(store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"])
    assert "empty answer" in text
    assert any(str(row.get("detail", {}).get("reason")) == "empty" for row in store.audit_log)


def test_repeated_tool_failures_stop_the_run() -> None:
    store = _store()
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [
                    {"id": f"c{index}", "name": "missing__tool", "arguments": {}}
                    for index in range(8)
                ],
                "usage": {"tokens_in": 1, "tokens_out": 1},
            }
        ],
    )
    run = _run(store, "Keep failing")
    assert run["status"] == "failed"
    text = str(store.messages[uuid.UUID(str(run["assistant_message_id"]))]["text"])
    assert "kept failing" in text


def test_complete_turn_reports_a_provider_error(monkeypatch: object) -> None:
    store = _store()

    class _Response:
        status_code = 503

        def json(self) -> dict[str, object]:
            return {}

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def post(self, *args: object, **kwargs: object) -> _Response:
            del args, kwargs
            return _Response()

    monkeypatch.setattr("ar_domain.chat.service.httpx.AsyncClient", _Client)
    parsed = asyncio.run(
        store.complete_turn(
            [{"role": "user", "content": "ping"}],
            [{"type": "function", "function": {"name": "session__search"}}],
            tenant_id=demo_id("tenant"),
            model_alias="reasoning",
        )
    )
    assert isinstance(parsed, dict)
    assert "error" in str(parsed["text"])


def test_reload_keeps_a_running_turn() -> None:
    from ar_domain.durable.hydrate import _merge_live

    current: dict[str, object] = {"status": "running", "result_summary": "kept"}
    _merge_live(current, {"status": "queued", "result_summary": None})
    assert current["status"] == "running"
    assert current["result_summary"] == "kept"
    _merge_live(current, {"status": "completed", "result_summary": "done"})
    assert current == {"status": "completed", "result_summary": "done"}


def test_complete_turn_reads_a_provider_response(monkeypatch: object) -> None:
    store = demo_store()

    class _Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def post(self, *args: object, **kwargs: object) -> _Response:
            del args, kwargs
            return _Response()

    monkeypatch.setattr("ar_domain.chat.service.httpx.AsyncClient", _Client)
    parsed = asyncio.run(
        store.complete_turn(
            [{"role": "user", "content": "ping"}],
            [],
            tenant_id=demo_id("tenant"),
            model_alias="reasoning",
        )
    )
    assert isinstance(parsed, dict)
    assert parsed["text"] == "pong"

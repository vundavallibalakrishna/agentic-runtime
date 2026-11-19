"""A run that a limit stopped keeps what it made, and the default token limit."""

import asyncio
import importlib
import uuid
from typing import TYPE_CHECKING

from ar_domain.agents.defaults import apply_definition_defaults
from ar_domain.agents.logic import assistant_definition, definition_hash
from ar_domain.demo_ids import demo_id
from ar_domain.runs.logic import DEFAULT_RUN_BUDGET
from ar_domain.tools.agent_loop import _stop_budget, budget_stop_text, read_budget
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_STOP = "Stopped because the max tokens limit was reached."


def _store(steps: list[dict[str, object]]) -> ChatService:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
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
    return store


def _write(call_id: str, path: str, tokens_in: int) -> dict[str, object]:
    return {
        "text": "",
        "tool_calls": [
            {
                "id": call_id,
                "name": "general__write_file",
                "arguments": {"path": path, "content": "a,b\n1,2\n"},
            }
        ],
        "usage": {"tokens_in": tokens_in, "tokens_out": 200},
    }


def _two_files_then_over() -> list[dict[str, object]]:
    # The second prompt is larger than the whole default limit, so the run stops before
    # a third model call, after both files were written.
    over = DEFAULT_RUN_BUDGET["max_tokens"] + 10_000
    return [_write("c1", "matrix.csv", 9_000), _write("c2", "sample.csv", over)]


def _post(store: ChatService) -> uuid.UUID:
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Make two files", schedule=False
    )
    return uuid.UUID(str(posted["run"]["id"]))


def _check_reply(store: ChatService, run_id: uuid.UUID) -> None:
    run = store.runs[run_id]
    assert run["status"] == "budget_exceeded"
    reply = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    assert reply["status"] == "completed"
    text = str(reply["text"])
    assert text.startswith(_STOP)
    assert "Done before the limit:" in text
    assert "- general.write_file: matrix.csv" in text
    assert "- general.write_file: sample.csv" in text
    content = reply["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": text}
    files = [part for part in content if part["type"] == "file"]
    assert [part["name"] for part in files] == ["matrix.csv", "sample.csv"]
    assert all(uuid.UUID(str(part["file_id"])) in store.files for part in files)
    calls = reply["tool_calls"]
    assert isinstance(calls, list)
    assert [call["status"] for call in calls] == ["succeeded", "succeeded"]
    assert run["result_summary"] == text
    kinds = [str(event["type"]) for event in store.events[run_id]]
    assert kinds[-2:] == ["message.completed", "run.budget_exceeded"]
    last = store.events[run_id][-1]
    assert last["data"] == {"limit": "max_tokens"}
    assert store.events[run_id][-2]["data"]["text"] == text
    conversation = store.conversations[uuid.UUID(str(run["conversation_id"]))]
    assert conversation["active_run_id"] is None


def test_a_stopped_run_keeps_the_files_its_tools_made() -> None:
    store = _store(_two_files_then_over())
    run_id = _post(store)
    asyncio.run(store.generate(run_id, "Make two files", []))
    _check_reply(store, run_id)


def test_a_run_a_worker_steps_keeps_them_too() -> None:
    store = _store(_two_files_then_over())
    run_id = _post(store)

    async def drive() -> list[str]:
        kinds: list[str] = []
        for _ in range(12):
            kinds.append(await store.advance_turn(run_id, "Make two files", []))
            if kinds[-1] in {"final", "paused"}:
                break
        return kinds

    kinds = asyncio.run(drive())
    assert kinds[-1] == "final"
    assert "tools" in kinds
    _check_reply(store, run_id)


def test_the_tool_call_limit_keeps_them_on_a_worker_step() -> None:
    store = _store([_write("c1", "matrix.csv", 9_000), _write("c2", "sample.csv", 9_500)])
    for version in store.versions.values():
        definition = version.get("definition")
        budget = definition.get("budget") if isinstance(definition, dict) else None
        if isinstance(budget, dict):
            budget["max_tool_calls"] = 1
    run_id = _post(store)

    async def drive() -> str:
        kind = ""
        for _ in range(12):
            kind = await store.advance_turn(run_id, "Make two files", [])
            if kind in {"final", "paused"}:
                break
        return kind

    assert asyncio.run(drive()) == "final"
    run = store.runs[run_id]
    assert run["status"] == "budget_exceeded"
    reply = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    text = str(reply["text"])
    assert text.startswith("Stopped because the max tool calls limit was reached.")
    assert "- general.write_file: matrix.csv" in text
    assert "sample.csv" not in text
    content = reply["content"]
    assert isinstance(content, list)
    assert [part["name"] for part in content if part["type"] == "file"] == ["matrix.csv"]


def test_the_stop_text_lists_only_what_succeeded() -> None:
    previews: list[dict[str, object]] = [
        {
            "qualified_name": "general.chart",
            "status": "succeeded",
            "presentation": {
                "kind": "chart",
                "title": "Revenue by month",
                "files": [{"file_id": "f-1", "name": "chart.png"}, {"name": " "}, "x"],
            },
        },
        {"qualified_name": "general.code", "status": "failed", "error": {"message": "boom"}},
        {"qualified_name": "knowledge.search", "status": "succeeded"},
        {"status": "succeeded", "presentation": {"title": " "}},
    ]
    text = budget_stop_text("max_wall_clock_s", previews)
    assert text.startswith("Stopped because the max wall clock s limit was reached.\n\n")
    assert "- Revenue by month: chart.png\n- knowledge.search\n- a tool call\n" in text
    assert "general.code" not in text and "boom" not in text
    nothing = budget_stop_text("max_steps", [previews[1]])
    assert nothing.startswith("Stopped because the max steps limit was reached.")
    assert "Nothing was finished before the limit." in nothing
    assert budget_stop_text("max_cost_micros", None) == (
        "Stopped because the max cost micros limit was reached."
    )


def test_a_stop_with_no_tool_calls_to_report_says_the_one_sentence() -> None:
    store = _store([])
    run_id = _post(store)
    run = store.runs[run_id]
    reply = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    before = reply.get("tool_calls")
    _stop_budget(store, run, reply, "max_tokens")
    assert reply["text"] == _STOP
    assert reply["content"] == [{"type": "text", "text": _STOP}]
    assert reply.get("tool_calls") == before
    assert run["status"] == "budget_exceeded"


def test_the_default_token_limit_is_one_number_everywhere() -> None:
    assert DEFAULT_RUN_BUDGET["max_tokens"] == 80_000
    assert read_budget({})["max_tokens"] == 80_000
    budget = assistant_definition()["budget"]
    assert budget == DEFAULT_RUN_BUDGET
    assert apply_definition_defaults({"instructions": "Help."})["budget"] == DEFAULT_RUN_BUDGET
    assert read_budget({"budget": {"max_tokens": 5}})["max_tokens"] == 5
    # The other limits are as they were.
    assert {key: value for key, value in DEFAULT_RUN_BUDGET.items() if key != "max_tokens"} == {
        "max_steps": 8,
        "max_cost_micros": 1_000_000,
        "max_wall_clock_s": 120,
        "max_tool_calls": 8,
        "max_parallel_tool_calls": 1,
    }


def _migration() -> object:
    return importlib.import_module(
        "ar_domain.migrations.versions.20261119_0054_assistant_token_budget"
    )


def test_the_migration_raises_the_seeded_token_limit() -> None:
    migration = _migration()
    old = assistant_definition()
    budget = old["budget"]
    assert isinstance(budget, dict)
    old["budget"] = {**budget, "max_tokens": 16_000}
    fresh = migration.with_limit(old, migration._OLD, migration._NEW)  # type: ignore[attr-defined]
    assert fresh is not None
    assert fresh == assistant_definition()
    assert migration._NEW == DEFAULT_RUN_BUDGET["max_tokens"]  # type: ignore[attr-defined]
    assert old["budget"]["max_tokens"] == 16_000
    assert migration._hash(fresh) == definition_hash(fresh)  # type: ignore[attr-defined]
    back = migration.with_limit(fresh, migration._NEW, migration._OLD)  # type: ignore[attr-defined]
    assert back == old


def test_the_migration_leaves_a_changed_limit_alone() -> None:
    migration = _migration()
    change = migration.with_limit  # type: ignore[attr-defined]
    assert change(assistant_definition(), 16_000, 80_000) is None
    assert change({"budget": {"max_tokens": 32_000}}, 16_000, 80_000) is None
    assert change({"budget": {"max_tokens": True}}, 1, 80_000) is None
    assert change({"budget": {"max_steps": 8}}, 16_000, 80_000) is None
    assert change({"budget": "none"}, 16_000, 80_000) is None
    assert change({}, 16_000, 80_000) is None
    kept = change({"budget": {"max_tokens": 16_000, "max_steps": 3}, "skills": ["a"]}, 16_000, 9)
    assert kept == {"budget": {"max_tokens": 9, "max_steps": 3}, "skills": ["a"]}
    assert migration._OURS == (  # type: ignore[attr-defined]
        "seed",
        "offline-default",
        "sample-and-saved-queries",
        "without-checkpoint",
    )
    assert migration._NOTE == "token-budget"  # type: ignore[attr-defined]

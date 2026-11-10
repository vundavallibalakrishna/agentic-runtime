"""Tools load on demand above the threshold, and a search is scoped to the agent. Task: M39-T04."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def _agent(store: Any, servers: list[str]) -> uuid.UUID:
    life = AgentLifecycle(store)
    created = life.create(_actor(), slug="ops", name="Ops", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    bindings = [{"server": slug, "include": ["*"]} for slug in servers]
    life.save_draft(_actor(), agent_id, {"instructions": "work", "tools": bindings})
    published = life.publish(_actor(), agent_id, change_note="bound")
    return uuid.UUID(str(published["published_version_id"]))


def _real_store() -> Any:
    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)
    return store


def test_many_tools_offer_the_search_tool_then_add_a_found_one() -> None:
    store = _real_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    # Built-in servers past the threshold. Not-live connector tools are not in this set.
    version_id = _agent(store, ["browser", "general", "documents", "knowledge", "data"])

    captured: list[list[str]] = []
    turns = [
        {
            "text": "",
            "tool_calls": [
                {"id": "c1", "name": "session__search", "arguments": {"query": "read a file"}}
            ],
            "usage": {"tokens_in": 2, "tokens_out": 2},
            "real": True,
        },
        {
            "text": "Found it.",
            "tool_calls": [],
            "usage": {"tokens_in": 2, "tokens_out": 2},
            "real": True,
        },
    ]

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tenant_id, model_alias
        captured.append([str(tool["function"]["name"]) for tool in tools])  # type: ignore[index]
        return turns.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]
    del version_id
    conversation = store.create_conversation(
        tenant, user, _agent_id(store), model_alias="reasoning"
    )
    conversation_id = uuid.UUID(str(conversation["id"]))
    posted = store.post_message(tenant, user, conversation_id, "find a tool", schedule=False)
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "find a tool", []))

    assert store.runs[run_id]["status"] == "completed"
    # The first call is not sent the whole catalogue; it gets the search tool.
    assert "session__search" in captured[0]
    assert len(captured[0]) < 20
    assert "general__read_file" not in captured[0]
    # The searched tool's schema joins the next call.
    assert "general__read_file" in captured[1]


def test_not_live_connector_tools_stay_hidden_from_the_model() -> None:
    store = _real_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    version_id = _agent(store, ["connectors"])
    captured: list[list[str]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tenant_id, model_alias
        captured.append([str(tool["function"]["name"]) for tool in tools])  # type: ignore[index]
        return {
            "text": "done",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
            "real": True,
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    conversation = store.create_conversation(
        tenant, user, _agent_id(store), model_alias="reasoning"
    )
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "find a tool", schedule=False
    )
    asyncio.run(store.generate(uuid.UUID(str(posted["run"]["id"])), "find a tool", []))
    names = captured[0]
    assert names
    assert all(
        name.startswith("connectors__email_") or name.startswith("connectors__github_")
        for name in names
    )
    result = dispatch(
        store,
        "builtin://session",
        "search",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_version_id": version_id,
            "query": "list buckets",
        },
        "",
    )
    found = [str(row["qualified_name"]) for row in result["structured"]["tools"]]
    assert not any("s3" in name or name.startswith("connectors.slack") for name in found)


def _agent_id(store: Any) -> uuid.UUID:
    return next(
        uuid.UUID(str(row["id"])) for row in store.agents.values() if row.get("slug") == "ops"
    )


def test_a_small_agent_is_not_deferred() -> None:
    store = _real_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    version_id = _agent(store, ["data"])  # 4 tools, under the threshold

    captured: list[int] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tenant_id, model_alias
        captured.append(len(tools))
        return {
            "text": "done",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
            "real": True,
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    conversation = store.create_conversation(
        tenant, user, _agent_id(store), model_alias="reasoning"
    )
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "hello", schedule=False
    )
    asyncio.run(store.generate(uuid.UUID(str(posted["run"]["id"])), "hello", []))
    del version_id
    # All four data tools are offered directly; nothing is deferred.
    assert captured[0] >= 4


def test_search_only_returns_tools_the_agent_is_granted() -> None:
    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    version_id = _agent(store, ["data"])  # bound to data only
    result = dispatch(
        store,
        "builtin://session",
        "search",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_version_id": version_id,
            "query": "list buckets",
        },
        "",
    )
    names = [str(row["qualified_name"]) for row in result["structured"]["tools"]]
    assert names  # the ranking returned something
    # A data-only agent never sees the connector tools, however well they match the query.
    assert not any(name.startswith("connectors.") for name in names)

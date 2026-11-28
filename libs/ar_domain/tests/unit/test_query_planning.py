"""A knowledge agent can ask the model for a few search queries before it searches."""

import uuid

import pytest

from ar_domain.knowledge.planning import plan_search_queries, planner_alias, wants_plan


class _Store:
    def __init__(self, text: str, *, connected: bool = True) -> None:
        self.text = text
        self.connected = connected
        self.aliases: list[str] = []

    def _completion_call(
        self, tenant_id: uuid.UUID, alias: str
    ) -> tuple[str, dict[str, str], float] | None:
        del tenant_id
        if not self.connected or alias == "missing":
            return None
        return (alias, {}, 5.0)

    async def complete_turn(
        self,
        messages: list[dict[str, object]],
        tools: list[object],
        **kwargs: object,
    ) -> dict[str, str]:
        del messages, tools
        self.aliases.append(str(kwargs.get("model_alias")))
        return {"text": self.text}


def test_planning_is_on_for_an_agent_with_a_library_and_off_when_told() -> None:
    assert wants_plan({"knowledge": {"collections": ["site"]}}) is True
    assert wants_plan({"knowledge": {"collections": ["site"], "planQueries": False}}) is False
    assert wants_plan({"knowledge": {"collections": []}}) is False
    assert wants_plan({"instructions": "Help."}) is False


def test_the_quick_alias_is_used_when_it_is_connected() -> None:
    tenant = uuid.uuid4()
    store = _Store("{}")
    definition = {
        "knowledge": {"collections": ["site"]},
        "model": {"alias": "reasoning", "fastAlias": "fast"},
    }
    assert planner_alias(store, tenant, definition) == "fast"
    store.connected = False
    assert planner_alias(store, tenant, definition) == "reasoning"
    named = {**definition, "knowledge": {"collections": ["site"], "plannerAlias": "quick"}}
    assert planner_alias(store, tenant, named) == "quick"


@pytest.mark.asyncio
async def test_the_model_reply_becomes_a_few_queries() -> None:
    tenant = uuid.uuid4()
    store = _Store('{"queries": ["desk hours", "desk hours", "north dock", "  "]}')
    found = await plan_search_queries(store, tenant, "fast", "When is the desk open?")
    assert found == ["desk hours", "north dock"]
    assert store.aliases == ["fast"]


@pytest.mark.asyncio
async def test_a_reply_that_is_not_queries_leaves_the_question_alone() -> None:
    tenant = uuid.uuid4()
    store = _Store("I would search for the desk.")
    assert await plan_search_queries(store, tenant, "fast", "When is the desk open?") is None
    quiet = _Store("{}", connected=False)
    assert await plan_search_queries(quiet, tenant, "fast", "When is the desk open?") is None

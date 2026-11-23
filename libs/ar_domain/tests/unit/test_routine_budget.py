"""A routine's own budget is a ceiling under its agent's budget."""

from __future__ import annotations

import uuid

from ar_domain.agents.access import Actor
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.routines.book import RoutineBook
from ar_domain.routines.engine import accept_routine_event, prepare_routine_run
from ar_domain.runs.dispatch import _budget
from ar_domain.runs.logic import DEFAULT_RUN_BUDGET
from ar_domain.tools.agent_loop import read_budget
from ar_testing.demo import demo_store

AGENT = {"budget": {"max_steps": 12, "max_tool_calls": 10, "max_tokens": 50_000}}


def test_a_routine_run_gets_the_lower_of_the_two_for_each_limit() -> None:
    tight = {"max_steps": 6, "max_tool_calls": 40, "max_wall_clock_s": 120, "max_cost_micros": 0}
    limits = read_budget(AGENT, {"trigger": "routine", "budget": tight})
    assert limits["max_steps"] == 6  # the routine is tighter
    assert limits["max_tool_calls"] == 10  # the routine cannot give more than the agent
    assert limits["max_wall_clock_s"] == 120
    assert limits["max_tokens"] == 50_000  # the routine names no token limit
    # A cost of 0 on a routine sets no cost ceiling; the agent's stays.
    assert limits["max_cost_micros"] == DEFAULT_RUN_BUDGET["max_cost_micros"]


def test_a_chat_run_and_a_routine_with_no_budget_keep_the_agents_limits() -> None:
    plain = read_budget(AGENT)
    assert read_budget(AGENT, {"trigger": "chat", "budget": {"max_steps": 1}}) == plain
    assert read_budget(AGENT, {"trigger": "routine", "budget": {}}) == plain
    assert read_budget(AGENT, {"trigger": "routine"}) == plain
    odd = {"max_steps": True, "max_tool_calls": "3", "unknown": 1}
    assert read_budget(AGENT, {"trigger": "routine", "budget": odd}) == plain


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def _run_of(store: object, routine_id: uuid.UUID) -> dict[str, object]:
    accepted = accept_routine_event(
        store,
        routine_id=routine_id,
        source="manual",
        idempotency_key=uuid.uuid4().hex,
        envelope={"type": "manual"},
    )
    prepared = prepare_routine_run(store, routine_id, uuid.UUID(str(accepted["event_id"])))
    return store.runs[uuid.UUID(str(prepared["run_id"]))]  # type: ignore[attr-defined,no-any-return]


def test_a_new_routine_adds_no_limit_until_someone_sets_one() -> None:
    store = demo_store()
    actor = _actor()
    agent = store.ensure_assistant(actor.tenant_id, actor.user_id)
    book = RoutineBook(store)
    body = {
        "name": "Plain",
        "agent_id": agent["id"],
        "instructions": "Say hello.",
        "trigger": {"type": "manual"},
    }
    plain = book.create(actor, body)
    assert plain["budget"] == DEFAULT_RUN_BUDGET
    run = _run_of(store, uuid.UUID(str(plain["id"])))
    agents_own = _budget(store, {**run, "trigger": "chat"})
    assert _budget(store, run) == agents_own

    tight = book.create(actor, {**body, "name": "Tight", "budget": {"max_tool_calls": 2}})
    held = _budget(store, _run_of(store, uuid.UUID(str(tight["id"]))))
    assert held["max_tool_calls"] == 2
    assert held["max_steps"] == agents_own["max_steps"]

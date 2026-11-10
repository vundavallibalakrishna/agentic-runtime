"""Cost comes from model prices and usage events carry run and model ids. Task: M32-T07."""

import asyncio
import uuid
from datetime import UTC, datetime

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.usage.logic import UsageRecord, model_cost_micros, usage_rows_to_flush
from ar_testing.demo import demo_store


def _priced_store() -> ChatService:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
    model = store.models[demo_id("model-chat")]
    model["price_input_micros_per_mtok"] = 150_000
    model["price_output_micros_per_mtok"] = 600_000
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


def test_cost_is_tokens_times_price_per_million() -> None:
    assert (
        model_cost_micros(1000, 500, price_in_per_mtok=150_000, price_out_per_mtok=600_000) == 450
    )
    assert model_cost_micros(1000, 500, price_in_per_mtok=0, price_out_per_mtok=0) == 0
    assert model_cost_micros(-5, 10, price_in_per_mtok=1, price_out_per_mtok=-1) == 0
    store = _priced_store()
    cost, model_id = store.model_cost(demo_id("tenant"), "reasoning", 1000, 500)
    assert (cost, model_id) == (450, str(demo_id("model-chat")))
    assert store.model_cost(demo_id("tenant"), "no-such-alias", 1000, 500) == (0, None)


def test_loop_prices_every_model_call_and_keeps_tokens_apart() -> None:
    store = _priced_store()
    _script(
        store,
        [
            {
                "text": "",
                "tool_calls": [
                    {"id": "c1", "name": "session__checkpoint", "arguments": {"note": "ready"}}
                ],
                "usage": {"tokens_in": 1000, "tokens_out": 100},
                "real": True,
            },
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": "c2",
                        "name": "session__checkpoint",
                        "arguments": {"note": "ready", "confirm": True},
                    }
                ],
                "usage": {"tokens_in": 2000, "tokens_out": 200},
                "real": True,
            },
            {
                "text": "Checkpoint saved: ready",
                "tool_calls": [],
                "usage": {"tokens_in": 3000, "tokens_out": 300},
                "real": True,
            },
        ],
    )
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Save a checkpoint", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "Save a checkpoint", []))
    run = store.runs[run_id]
    assert run["status"] == "completed"
    usage = run["usage"]
    assert usage["tokens_in"] == 6000
    assert usage["tokens_out"] == 600
    # 6000 * 150_000 + 600 * 600_000, over one million.
    assert usage["cost_micros"] == 900 + 360
    events = [item for item in store.usage.values() if item.run_id == str(run_id)]
    inputs = sorted(item.quantity for item in events if item.metric == "model_input_tokens")
    outputs = sorted(item.quantity for item in events if item.metric == "model_output_tokens")
    assert inputs == [1000, 2000, 3000]
    assert outputs == [100, 200, 300]
    assert {item.model_alias for item in events} == {"reasoning"}
    assert {item.model_id for item in events} == {str(demo_id("model-chat"))}
    assert sum(item.cost_micros for item in events) == 1260
    assert all(item.source == "model-gateway" for item in events)


def test_only_unflushed_rows_of_the_bound_tenant_are_written() -> None:
    bound, other = str(uuid.uuid4()), str(uuid.uuid4())
    early = datetime(2026, 1, 1, tzinfo=UTC)
    late = datetime(2026, 1, 2, tzinfo=UTC)
    usage = {
        (bound, "b-late"): UsageRecord(bound, late, "runs", 1, 0, "b-late"),
        (bound, "b-early"): UsageRecord(bound, early, "runs", 1, 0, "b-early"),
        (bound, "b-done"): UsageRecord(bound, early, "runs", 1, 0, "b-done"),
        (other, "o-1"): UsageRecord(other, early, "runs", 1, 0, "o-1"),
    }
    rows = usage_rows_to_flush(usage, {(bound, "b-done")}, uuid.UUID(bound))
    assert [key for key, _ in rows] == [(bound, "b-early"), (bound, "b-late")]
    record = UsageRecord(bound, early, "runs", 1, 0, "x")
    assert record.run_id is None and record.model_id is None and record.tool_id is None


def _cap(store: ChatService, max_tokens: int) -> None:
    for version in store.versions.values():
        definition = version.get("definition")
        budget = definition.get("budget") if isinstance(definition, dict) else None
        if isinstance(budget, dict):
            budget["max_tokens"] = max_tokens


def test_budget_stop_keeps_the_usage_spent_so_far() -> None:
    store = _priced_store()
    # The budget counts prompt growth, not the whole prompt again. A repeated
    # 7_000-token prompt only adds output after the first step, so the cap has
    # to sit on that first charge to prove a stop still records usage.
    _cap(store, 7100)
    tool_turn = {
        "text": "",
        "tool_calls": [{"id": "c1", "name": "session__checkpoint", "arguments": {"note": "x"}}],
        "usage": {"tokens_in": 7000, "tokens_out": 100},
        "real": True,
    }
    _script(store, [tool_turn, dict(tool_turn), dict(tool_turn), dict(tool_turn)])
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Loop until the budget", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "Loop until the budget", []))
    run = store.runs[run_id]
    assert run["status"] == "budget_exceeded"
    usage = run["usage"]
    assert usage["tokens_in"] >= 14000
    assert usage["tokens_out"] >= 200
    assert usage["cost_micros"] > 0


def test_six_step_turn_does_not_recount_the_prompt() -> None:
    """A growing prompt is charged once. Recounting each step exceeds 16k."""
    store = _priced_store()
    steps: list[dict[str, object]] = []
    reported = [3000, 4500, 6000, 7500, 9000, 10500]
    for index, tokens_in in enumerate(reported):
        steps.append(
            {
                "text": "",
                "tool_calls": [
                    {
                        "id": f"c{index}",
                        "name": "session__checkpoint",
                        "arguments": {"note": str(index)},
                    }
                ],
                "usage": {"tokens_in": tokens_in, "tokens_out": 100},
                "real": True,
            }
        )
    steps.append(
        {
            "text": "Done.",
            "tool_calls": [],
            "usage": {"tokens_in": 12000, "tokens_out": 100},
            "real": True,
        }
    )
    _script(store, steps)
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Six tool steps", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "Six tool steps", []))
    run = store.runs[run_id]
    assert run["status"] == "completed"
    usage = run["usage"]
    assert usage["tokens_in"] == sum(reported) + 12000
    assert usage["tokens_out"] == 700

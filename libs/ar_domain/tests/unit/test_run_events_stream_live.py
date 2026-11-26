"""A turn's text reaches the run-event stream while the model is still writing it."""

import asyncio
import threading
import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

from ar_common.settings import EnvName
from ar_domain.demo_ids import demo_id
from ar_domain.models.streaming import listener
from ar_domain.runs.event_bus import ValkeyRunBus, process_bus
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


class _Stream:
    """Records each write with the loop it ran on."""

    def __init__(self) -> None:
        self.added: list[tuple[str, int]] = []

    async def xadd(self, key: str, fields: dict[str, str], **_options: object) -> str:
        import orjson

        event = orjson.loads(fields["payload"])
        self.added.append((str(event["type"]), id(asyncio.get_running_loop())))
        return f"{len(self.added)}-0"


def test_only_processes_that_share_state_get_a_bus() -> None:
    assert process_bus(SimpleNamespace(env=EnvName.DEV, valkey_url="redis://x")) is None
    assert process_bus(SimpleNamespace(env=EnvName.CI, valkey_url="redis://x")) is None
    shared = process_bus(SimpleNamespace(env=EnvName.STAGING, valkey_url="redis://x/0"))
    assert isinstance(shared, ValkeyRunBus)
    assert shared.url == "redis://x/0"


def test_a_write_from_another_threads_loop_runs_on_the_owner_loop() -> None:
    stream = _Stream()
    bus = ValkeyRunBus("redis://unused", client=stream)
    run_id = uuid.uuid4()

    async def main() -> int:
        owner = id(asyncio.get_running_loop())
        bus.publish(run_id, {"type": "run.started", "seq": 1})

        def elsewhere() -> None:
            async def emit() -> None:
                bus.publish(run_id, {"type": "tool_call.completed", "seq": 2})

            asyncio.run(emit())

        thread = threading.Thread(target=elsewhere)
        thread.start()
        await asyncio.to_thread(thread.join)
        # The handed-over write runs on this loop once it is free to.
        for _ in range(100):
            if len(stream.added) == 2:
                break
            await asyncio.sleep(0)
        return owner

    owner = asyncio.run(main())
    assert [kind for kind, _loop in stream.added] == ["run.started", "tool_call.completed"]
    # Both writes used the client on the loop it belongs to.
    assert {loop for _kind, loop in stream.added} == {owner}


def _store(stream: _Stream, published_mid_call: list[int]) -> ChatService:
    store = demo_store()
    store.event_bus = ValkeyRunBus("redis://unused", client=stream)
    store._completion_call = lambda _tenant, alias="reasoning": ("m", {}, 5.0)  # type: ignore[method-assign]

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tools, tenant_id, model_alias
        sink = listener()
        assert sink is not None, "the step listens for the answer as it is written"
        words = ["Banks ", "and ", "insurers ", "are ", "covered."]
        for word in words:
            sink(word)
            # The model is still writing. What it wrote so far is already on the stream.
            await asyncio.sleep(0.06)
        published_mid_call.append(sum(kind == "message.delta" for kind, _ in stream.added))
        return {
            "text": "".join(words),
            "tool_calls": [],
            "usage": {"tokens_in": 10, "tokens_out": 5},
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    return store


def test_a_worker_step_streams_the_answer_while_it_is_written() -> None:
    stream = _Stream()
    mid_call: list[int] = []
    store = _store(stream, mid_call)
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Who do you serve?", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))

    async def steps() -> None:
        for _ in range(8):
            if await store.advance_turn(run_id, "Who do you serve?", []) in {"final", "paused"}:
                break
        bus = store.event_bus
        assert isinstance(bus, ValkeyRunBus)
        if bus._pending:
            await asyncio.gather(*list(bus._pending))

    asyncio.run(steps())

    assert store.runs[run_id]["status"] == "completed"
    # Before the model call ended, several pieces of its text had been published.
    assert mid_call and mid_call[0] >= 3
    kinds = [kind for kind, _ in stream.added]
    assert kinds.index("message.delta") < kinds.index("run.completed")

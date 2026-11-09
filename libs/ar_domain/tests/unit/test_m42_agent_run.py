"""One-shot agent run and cost in the /v1 reply. Stage F/G of M42.

Spec: docs/06-security/m29-exposure.md, docs/agent-api/getting-started.md.
"""

from __future__ import annotations

import uuid

import pytest

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.exposure import keys, runs
from ar_testing.demo import demo_store


def _store() -> ChatService:
    store = demo_store()
    store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    return store


async def _answer(store: ChatService, run_id: uuid.UUID, text: str, names: list[str]) -> None:
    del text, names
    run = store.runs[run_id]
    run["status"] = "completed"
    run["usage"] = {"tokens_in": 11, "tokens_out": 7, "cost_micros": 420, "model_calls": 1}
    assistant = store.messages[run["assistant_message_id"]]
    assistant["text"] = "4"
    assistant["status"] = "completed"


def _key(store: ChatService) -> dict:
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    row, _secret = keys.create_key(
        store, tenant_id=demo_id("tenant"), agent_id=agent["id"],
        user_id=demo_id("admin"), label="run",
    )
    return row


@pytest.mark.asyncio
async def test_run_once_creates_conversation_and_returns_usage() -> None:
    store = _store()

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        await _answer(store, run_id, text, names)

    store.generate = generate  # type: ignore[method-assign]
    key = _key(store)
    reply, replayed = await runs.run_once(store, key, "assistant", "What is 2 + 2?", [], "")
    assert replayed is False
    assert reply["output"] == "4"
    # A fresh conversation was created for the one-shot run.
    assert reply["conversation_id"]
    # The reply surfaces token and cost usage for the integrator.
    assert reply["usage"]["tokens_in"] == 11
    assert reply["usage"]["cost_micros"] == 420
    assert "model_calls" in reply["usage"] and "tool_calls" in reply["usage"]


@pytest.mark.asyncio
async def test_run_once_is_idempotent() -> None:
    store = _store()

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        await _answer(store, run_id, text, names)

    store.generate = generate  # type: ignore[method-assign]
    key = _key(store)
    first, replayed = await runs.run_once(store, key, "assistant", "hi", [], "once")
    assert replayed is False
    again, replayed = await runs.run_once(store, key, "assistant", "hi", [], "once")
    assert replayed is True and again["id"] == first["id"]

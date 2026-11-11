"""The flows the certification failed: structured output, citations and approval. Proof: unit."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ar_domain.chat.service import demo_id
from ar_testing.demo import demo_store

_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"capital": {"type": "string"}},
    "required": ["capital"],
    "additionalProperties": False,
}


def _turn(text: str) -> dict[str, object]:
    return {
        "text": text,
        "tool_calls": [],
        "usage": {"tokens_in": 1, "tokens_out": 1},
        "real": True,
    }


def _structured_run(
    replies: list[str],
) -> tuple[Any, dict[str, object], list[list[dict[str, object]]]]:
    """Run one turn that asks for ``_SCHEMA`` against the given model replies."""
    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("model", {}, 5.0, True)
    seen: list[list[dict[str, object]]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del tools, tenant_id, model_alias
        seen.append([dict(message) for message in messages])
        return _turn(replies.pop(0))

    store.complete_turn = complete
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "What is the capital of France?",
        schedule=False,
        response_format=_SCHEMA,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "What is the capital of France?", []))
    return store, store.runs[run_id], seen


def _answer(store: Any, run: dict[str, object]) -> str:
    rows = [
        row
        for row in store.messages.values()
        if row.get("run_id") == run["id"] and row.get("role") == "assistant"
    ]
    return str(rows[-1].get("text") or "") if rows else ""


def test_the_model_is_told_the_schema_the_caller_asked_for() -> None:
    store, run, seen = _structured_run(['{"capital": "Paris"}'])
    assert run["status"] == "completed"
    assert _answer(store, run) == '{"capital":"Paris"}'
    told = " ".join(str(message.get("content") or "") for message in seen[0])
    assert "Return only JSON matching this schema" in told
    assert '"capital"' in told


def test_a_reply_that_misses_the_schema_is_sent_back_with_the_schema() -> None:
    wrong = '{"name": "session__search", "arguments": {"query": "capital of France"}}'
    store, run, seen = _structured_run([wrong, '{"capital": "Paris"}'])
    assert run["status"] == "completed"
    assert _answer(store, run) == '{"capital":"Paris"}'
    retry = str(seen[1][-1].get("content") or "")
    assert "not a tool call written as text" in retry
    assert '"capital"' in retry


def test_a_reply_that_never_matches_is_not_stored_as_the_answer() -> None:
    wrong = '{"name": "session__search", "arguments": {}}'
    store, run, _seen = _structured_run([wrong, wrong])
    assert run["status"] == "failed"
    assert run["error"]["code"] == "repair_exhausted"
    assert "session__search" not in _answer(store, run)


_POLICY = (
    "# Access control policy\n\n"
    "## Break-glass access\n\n"
    "Break-glass access is allowed for 4 hours and must be approved by the duty manager.\n\n"
    "## Retention\n\n"
    "Access logs are kept for 7 years.\n"
)


def _attached_turn(reply: str) -> tuple[Any, dict[str, object], list[dict[str, object]]]:
    """One turn over an attached policy file. Returns the store, the run and the prompt."""
    from ar_domain.agents.access import Actor
    from ar_domain.documents.library import ingest_bytes
    from ar_domain.identity.permissions import PERMISSION_KEYS

    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("model", {}, 5.0, True)
    tenant, user = demo_id("tenant"), demo_id("admin")
    upload = store.upload(tenant, user, "access-policy.md", "text/markdown", _POLICY.encode())
    asyncio.run(
        ingest_bytes(
            store,
            Actor(tenant, user, PERMISSION_KEYS),
            data=_POLICY.encode(),
            filename="access-policy.md",
            media_type="text/markdown",
        )
    )
    seen: list[dict[str, object]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del tools, tenant_id, model_alias
        seen.extend(dict(message) for message in messages)
        return _turn(reply)

    store.complete_turn = complete
    conversation = store.create_conversation(tenant, user, None)
    question = "How long is break-glass access allowed? Cite the passage."
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        question,
        schedule=False,
        attachment_ids=[uuid.UUID(str(upload["id"]))],
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, question, []))
    return store, store.runs[run_id], seen


def _assistant(store: Any, run: dict[str, object]) -> dict[str, object]:
    return next(
        row
        for row in store.messages.values()
        if row.get("run_id") == run["id"] and row.get("role") == "assistant"
    )


def test_an_attached_passage_is_shown_with_its_anchor_and_cited_as_a_part() -> None:
    store, run, seen = _attached_turn("Break-glass access is allowed for 4 hours [p1-s0 p.1].")
    prompt = " ".join(str(message.get("content") or "") for message in seen)
    # The model sees each passage after its anchor, and is told to cite it.
    assert "[p1-s0 p.1] Break-glass access is allowed for 4 hours" in prompt
    assert "put that anchor after the statement" in prompt
    assert run["status"] == "completed"
    cited = [part for part in _assistant(store, run)["content"] if part["type"] == "citation_ref"]
    assert len(cited) == 1
    citation = cited[0]["citation"]
    assert citation["anchor"] == "p1-s0"
    assert citation["source_kind"] == "document"
    assert "duty manager" in citation["snippet"]
    assert citation["uri"].endswith("#p1-s0")
    added = [event for event in store.events[run["id"]] if event["type"] == "citation.added"]
    assert added


def test_an_anchor_no_attached_document_holds_is_not_a_citation() -> None:
    store, run, _seen = _attached_turn("It is allowed for 4 hours [p9-s9 p.9].")
    parts = _assistant(store, run)["content"]
    assert [part["type"] for part in parts] == ["text"]

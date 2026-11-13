"""A message of several questions is searched question by question. Proof: unit."""

from __future__ import annotations

import asyncio
import uuid

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.members import _fused, add_member, message_queries, retrieve
from ar_domain.workspace.turn import _top_k
from ar_testing.demo import demo_store


def test_a_plain_message_is_one_query() -> None:
    assert message_queries("What is the dock code?") == ["What is the dock code?"]
    prose = "Tell me about the docks.\nI need it for the handover."
    assert message_queries(prose) == [prose]


def test_a_list_of_questions_is_one_query_each() -> None:
    text = "Answer these from the library.\n\nQ1. Is data encrypted?\nQ2. Who audits you?\n- Where?"
    assert message_queries(text) == ["Q1. Is data encrypted?", "Q2. Who audits you?", "- Where?"]
    many = "\n".join(f"{index}. question {index}?" for index in range(1, 40))
    assert len(message_queries(many)) == 20


def test_fusing_takes_each_querys_best_hit_before_any_second_hit() -> None:
    first = [{"chunk_id": "a"}, {"chunk_id": "b"}]
    second = [{"chunk_id": "a"}, {"chunk_id": "c"}]
    third: list[dict[str, object]] = []
    assert [hit["chunk_id"] for hit in _fused([first, second, third])] == ["a", "b", "c"]


def test_the_agents_own_top_k_is_used() -> None:
    assert _top_k({"knowledge": {"top_k": 3}}) == 3
    assert _top_k({"knowledge": {"top_k": "many"}}) == _top_k({})
    assert _top_k({}) > 0


def _library(store: object, tenant: uuid.UUID, title: str, text: str) -> uuid.UUID:
    document_id = uuid.uuid4()
    store.library_documents[document_id] = {  # type: ignore[attr-defined]
        "id": document_id,
        "tenant_id": tenant,
        "title": title,
        "content_hash": title,
        "passages": [{"text": text, "anchor": "p1-s0", "page": 1, "heading": title}],
    }
    return document_id


def test_each_question_brings_its_own_passage() -> None:
    store = demo_store()
    actor = Actor(
        demo_id("tenant"),
        demo_id("admin"),
        frozenset({"knowledge:manage", "knowledge:read", "chat:use"}),
    )
    created = KnowledgeBook(store).create_collection(actor, {"name": "Trust", "slug": "trust"})
    collection_id = uuid.UUID(created["id"])
    texts = {
        "Encryption": "Customer data is encrypted at rest with AES-256.",
        "Audit report": "The service auditor issued an unqualified opinion for the period.",
    }
    for title, text in texts.items():
        library_id = _library(store, actor.tenant_id, title, text)
        asyncio.run(
            add_member(
                store,
                actor,
                collection_id,
                {"kind": "library", "library_document_id": str(library_id)},
            )
        )
    message = (
        "Answer from the library.\n"
        "1. Is customer data encrypted at rest?\n"
        "2. What opinion did the service auditor issue?"
    )
    found = asyncio.run(retrieve(store, actor, [collection_id], message, top_k=1))
    shown = " ".join(str(hit.get("text")) for hit in found["hits"])  # type: ignore[union-attr]
    assert "AES-256" in shown
    assert "unqualified opinion" in shown
    assert len(found["trace"]["queries"]) == 2  # type: ignore[index, arg-type]
    single = asyncio.run(retrieve(store, actor, [collection_id], "Is data encrypted?", top_k=1))
    assert single["trace"]["queries"] == []  # type: ignore[index]
    assert len(single["hits"]) == 1  # type: ignore[arg-type]

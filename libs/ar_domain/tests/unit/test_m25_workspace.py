"""Knowledge bases, memory compaction and portable skills."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.vectors import unit_vector
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.live_embed import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingUnconfiguredError,
    collection_embedding,
    embed_live,
    is_fake_embedding,
)
from ar_domain.knowledge.members import add_member, refresh_document, retrieve
from ar_domain.memory.session import prepare_prompt
from ar_domain.skills.match import match_skill
from ar_domain.skills.portable import export_skill, import_skill, parse_markdown
from ar_domain.workspace.turn import ground_run
from ar_testing.demo import demo_store

_MARKDOWN = """---
name: Weekly status
slug: weekly-status
description: Use when the user asks for a weekly status note in the house style.
examples: Draft the weekly status
---

Begin with the token STATUS-OK and use three short sentences.
"""


def _actor() -> Actor:
    return Actor(
        demo_id("tenant"),
        demo_id("admin"),
        frozenset(
            {
                "knowledge:manage",
                "knowledge:read",
                "skills:create",
                "skills:read",
                "skills:manage_all",
                "chat:use",
            }
        ),
    )


def _vectors(texts: list[str]) -> list[list[float]]:
    return [unit_vector(text, 1024) for text in texts]


def test_fake_alias_is_not_a_live_embedding() -> None:
    assert is_fake_embedding("fake-embed")
    assert is_fake_embedding("embed")
    store = demo_store()
    with pytest.raises(EmbeddingUnconfiguredError):
        embed_live(store, demo_id("tenant"), ["north dock"], model="fake-embed", dimensions=1024)
    with pytest.raises(EmbeddingUnconfiguredError):
        embed_live(store, demo_id("tenant"), ["north dock"], model="BAAI/bge-m3", dimensions=1024)


def test_a_real_provider_selects_the_default_model() -> None:
    store = demo_store()
    provider_id = uuid.uuid4()
    store.providers[provider_id] = {
        "id": provider_id,
        "tenant_id": demo_id("tenant"),
        "kind": "openai_compatible",
        "base_url": "https://embeddings.example/v1",
        "api_key": "test-key",
    }
    store.embed_client = _vectors
    actor = _actor()
    created = KnowledgeBook(store).create_collection(
        actor, {"name": "Docks", "slug": "docks", "description": "Dock codes"}
    )
    row = store.knowledge_collections[uuid.UUID(created["id"])]
    assert row["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert row["embedding_model"] != "fake-embed"
    assert collection_embedding({"chunking": row["chunking"], "embedding_alias": "embed"})[0] == (
        DEFAULT_EMBEDDING_MODEL
    )


def test_library_url_and_connection_round_trip() -> None:
    store = demo_store()
    store.embed_client = _vectors
    actor = _actor()
    library_id = uuid.uuid4()
    store.library_documents[library_id] = {
        "id": library_id,
        "tenant_id": actor.tenant_id,
        "title": "Dock notes",
        "content_hash": "abc",
        "passages": [
            {
                "text": "The warehouse code for the north dock is ND-1844-QUILL.",
                "anchor": "p1-s1",
                "page": 1,
                "heading": "Docks",
            },
            {
                "text": "The south dock uses a different badge colour.",
                "anchor": "p2-s1",
                "page": 2,
                "heading": "Docks",
            },
        ],
    }
    created = KnowledgeBook(store).create_collection(
        actor, {"name": "Docks", "slug": "docks", "description": "Dock codes"}
    )
    collection_id = uuid.UUID(created["id"])
    indexed = asyncio.run(
        add_member(
            store,
            actor,
            collection_id,
            {"kind": "library", "library_document_id": str(library_id)},
        )
    )
    assert indexed["result"] == "indexed"
    assert indexed["chunks"] == 2
    again = asyncio.run(
        add_member(
            store,
            actor,
            collection_id,
            {"kind": "library", "library_document_id": str(library_id)},
        )
    )
    assert again["result"] == "unchanged"
    found = asyncio.run(
        retrieve(store, actor, [collection_id], "What is the warehouse code for the north dock?")
    )
    assert found["answerable"] is True
    assert found["trace"]["used_chars"] <= 12_000
    top = found["hits"][0]
    assert top["anchor"] == "p1-s1"
    assert top["page"] == 1
    assert "ND-1844-QUILL" in str(top["text"])

    store.library_documents[library_id]["passages"][0]["text"] = (
        "The warehouse code for the north dock is ND-2000-REED."
    )
    refreshed = asyncio.run(refresh_document(store, actor, uuid.UUID(indexed["document"]["id"])))
    assert refreshed["result"] == "indexed"
    again_found = asyncio.run(
        retrieve(store, actor, [collection_id], "warehouse code for the north dock")
    )
    assert "ND-2000-REED" in str(again_found["hits"][0]["text"])

    def send(
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, object] | None = None,
        json_body: object = None,
        timeout: int = 30,
    ) -> tuple[int, str]:
        del method, headers, params, json_body, timeout
        assert url == "https://example.com/notes"
        return 200, "The visitor desk opens at 07:15."

    store.http_send = send
    url_added = asyncio.run(
        add_member(
            store,
            actor,
            collection_id,
            {"kind": "url", "url": "https://example.com/notes", "title": "Desk"},
        )
    )
    assert url_added["result"] == "indexed"
    with pytest.raises(ValidationFailedError):
        asyncio.run(
            add_member(
                store, actor, collection_id, {"kind": "url", "url": "http://127.0.0.1/secret"}
            )
        )
    other = Actor(uuid.uuid4(), uuid.uuid4(), frozenset({"knowledge:manage", "knowledge:read"}))
    with pytest.raises(NotFoundError):
        asyncio.run(
            add_member(
                store,
                other,
                collection_id,
                {"kind": "library", "library_document_id": str(library_id)},
            )
        )


def test_skill_import_matches_and_exports() -> None:
    store = demo_store()
    actor = _actor()
    imported = import_skill(store, actor, markdown=_MARKDOWN)
    assert imported["slug"] == "weekly-status"
    assert imported["status"] == "published"
    parsed = parse_markdown(_MARKDOWN)
    assert "STATUS-OK" in str(parsed["instructions"])
    exported = export_skill(store, actor, imported["id"])
    assert "weekly-status" in str(exported["markdown"])
    assert exported["archive_b64"]
    skill = store.skills[uuid.UUID(str(imported["id"]))]
    version_id = uuid.UUID(str(skill["published_version_id"]))
    assets = store.skill_versions[version_id]["assets"]
    assert any(item.get("path") == "examples.txt" for item in assets)
    agent_id = uuid.uuid4()
    version = uuid.uuid4()
    store.versions[version] = {
        "id": version,
        "definition": {"skills": ["weekly-status"], "instructions": "Help."},
    }
    run = {
        "id": uuid.uuid4(),
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "agent_version_id": version,
        "agent_id": agent_id,
        "conversation_id": uuid.uuid4(),
    }
    loaded = match_skill(
        store, run, store.versions[version]["definition"], "Write the weekly status note"
    )
    assert loaded is not None
    assert loaded["slug"] == "weekly-status"
    assert "status" in loaded["reason"]
    missed = match_skill(store, run, store.versions[version]["definition"], "What is the weather?")
    assert missed is None


def test_turn_cites_a_passage_and_stays_inside_the_budget() -> None:
    store = demo_store()
    store.embed_client = _vectors
    actor = _actor()
    created = KnowledgeBook(store).create_collection(
        actor, {"name": "Policy", "slug": "policy", "description": "Rules"}
    )
    collection_id = uuid.UUID(created["id"])
    pages = [
        {
            "text": f"Page {number} discusses control AC-{number}. " + ("detail " * 40),
            "anchor": f"p{number}",
            "page": number,
            "heading": "Controls",
        }
        for number in range(1, 41)
    ]
    pages[17]["text"] = "Page 18 names the recovery code RECOVER-18-ONLY for the archive room."
    library_id = uuid.uuid4()
    store.library_documents[library_id] = {
        "id": library_id,
        "tenant_id": actor.tenant_id,
        "title": "Controls",
        "passages": pages,
    }
    asyncio.run(
        add_member(
            store,
            actor,
            collection_id,
            {"kind": "library", "library_document_id": str(library_id)},
        )
    )
    version = uuid.uuid4()
    store.versions[version] = {
        "id": version,
        "definition": {
            "instructions": "Answer from the library.",
            "knowledge": {"collections": ["policy"]},
            "context_window": 2000,
            "context": {"compaction_threshold": 0.5, "keep_messages": 4},
        },
    }
    conversation_id = uuid.uuid4()
    store.conversations[conversation_id] = {"id": conversation_id, "rolling_summary": ""}
    run = {
        "id": uuid.uuid4(),
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "agent_version_id": version,
        "conversation_id": conversation_id,
        "input_message_id": uuid.uuid4(),
    }
    for index in range(8):
        message_id = uuid.uuid4()
        store.messages[message_id] = {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": "user",
            "text": f"turn {index} " + ("word " * 400),
            "status": "completed",
            "created_at": f"2026-11-04T00:00:{index:02d}+00:00",
        }
    prepare_prompt(
        store,
        run,
        store.conversations[conversation_id],
        store.versions[version]["definition"],
        "Where is the recovery code?",
        names=[],
    )
    assert run["compaction"]["strategy"] == "summary"
    assert run["compaction"]["keep_messages"] == 4
    asyncio.run(ground_run(store, run, "Where is the recovery code for the archive room?"))
    trace = run["retrieval"]
    assert trace["used_chars"] <= 12_000
    assert any(hit["anchor"] == "p18" for hit in trace["hits"])
    system = str(run["prompt_messages"][0]["content"])
    assert "RECOVER-18-ONLY" in system
    assert "untrusted_content" in system
    bare = {
        **run,
        "id": uuid.uuid4(),
        "agent_version_id": version,
        "retrieval": None,
        "loaded_skill": None,
        "prompt_messages": [{"role": "system", "content": "Help."}],
    }
    store.versions[version]["definition"] = {
        "instructions": "Help.",
        "knowledge": {"collections": []},
    }
    asyncio.run(ground_run(store, bare, "Where is the recovery code?"))
    assert "do not invent" in str(bare["prompt_messages"][0]["content"]).lower()
    assert "RECOVER-18-ONLY" not in str(bare["prompt_messages"][0]["content"])

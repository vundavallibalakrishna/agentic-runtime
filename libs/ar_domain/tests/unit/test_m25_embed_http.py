"""HTTP embedding, rerank and portable skill archives."""

from __future__ import annotations

import asyncio
import io
import uuid
import zipfile

import pytest

from ar_common.errors import ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.members import add_member, refresh_document
from ar_domain.skills.portable import import_skill, parse_markdown
from ar_domain.workspace.turn import citation_parts, ground_run, has_grounding, opening_messages
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
        frozenset({"knowledge:manage", "knowledge:read", "skills:create", "skills:read"}),
    )


def test_text_member_is_unchanged_until_refresh() -> None:
    store = demo_store()
    actor = _actor()
    created = KnowledgeBook(store).create_collection(
        actor,
        {
            "name": "Notes",
            "slug": "notes",
            "description": "Notes",
            "embedding_alias": "embed",
        },
    )
    collection_id = uuid.UUID(created["id"])
    first = asyncio.run(
        add_member(
            store,
            actor,
            collection_id,
            {"kind": "text", "title": "Note", "text": "The badge colour is blue."},
        )
    )
    assert first["result"] == "indexed"
    second = asyncio.run(
        add_member(
            store,
            actor,
            collection_id,
            {"kind": "text", "title": "Note", "text": "The badge colour is blue."},
        )
    )
    assert second["result"] == "unchanged"
    document_id = uuid.UUID(str(first["document"]["id"]))
    store.knowledge_blobs[document_id] = b"The badge colour is green."
    refreshed = asyncio.run(refresh_document(store, actor, document_id))
    assert refreshed["result"] == "indexed"
    with pytest.raises(ValidationFailedError):
        asyncio.run(add_member(store, actor, collection_id, {"kind": "nope"}))
    with pytest.raises(ValidationFailedError):
        asyncio.run(add_member(store, actor, collection_id, {"kind": "text", "text": "  "}))


def test_zip_import_keeps_helper_files() -> None:
    store = demo_store()
    actor = _actor()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("folder/SKILL.md", _MARKDOWN)
        book.writestr("folder/helper.txt", "house style")
        book.writestr("folder/../escape.txt", "no")
    imported = import_skill(store, actor, archive=buffer.getvalue())
    assert imported["slug"] == "weekly-status"
    with pytest.raises(ValidationFailedError):
        import_skill(store, actor, archive=b"not-a-zip")
    heading = import_skill(
        store,
        actor,
        markdown="# House voice\n\nAlways sign off with the word Done.",
    )
    assert heading["slug"]
    with pytest.raises(ValidationFailedError):
        parse_markdown("---\nname: Empty\n---\n\n")
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as book:
        book.writestr("notes.txt", "no skill here")
    with pytest.raises(ValidationFailedError):
        import_skill(store, actor, archive=empty.getvalue())


def test_member_edges_and_connection_redaction() -> None:
    store = demo_store()
    actor = _actor()
    created = KnowledgeBook(store).create_collection(
        actor,
        {"name": "Edges", "slug": "edges", "description": "Edges", "embedding_alias": "embed"},
    )
    collection_id = uuid.UUID(created["id"])
    with pytest.raises(ValidationFailedError):
        asyncio.run(
            add_member(
                store,
                actor,
                collection_id,
                {"kind": "library", "library_document_id": "no"},
            )
        )

    def send(
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> tuple[int, str]:
        del method, headers, timeout
        if url.endswith("/missing"):
            return 404, ""
        return 200, "The token secret-token opens the side door."

    store.http_send = send
    with pytest.raises(ValidationFailedError):
        asyncio.run(
            add_member(
                store, actor, collection_id, {"kind": "url", "url": "https://example.com/missing"}
            )
        )

    class _Book:
        def __init__(self, _store: object) -> None:
            del _store

        def _own(self, _actor: object, connection_id: uuid.UUID) -> dict[str, str]:
            del _actor
            return {"name": "Desk", "probe_url": f"https://example.com/{connection_id}"}

    import ar_domain.tools.service_connections as connections

    original_book = connections.ConnectionBook
    original_headers = connections._headers
    connections.ConnectionBook = _Book  # type: ignore[misc]
    connections._headers = lambda _row: ({"Authorization": "Bearer secret-token"}, "secret-token")  # type: ignore[assignment]
    try:
        added = asyncio.run(
            add_member(
                store,
                actor,
                collection_id,
                {"kind": "connection", "connection_id": str(uuid.uuid4())},
            )
        )
    finally:
        connections.ConnectionBook = original_book
        connections._headers = original_headers
    assert added["result"] == "indexed"
    assert "secret-token" not in str(added["document"])


def test_grounding_records_a_skill_and_citation_cards() -> None:
    store = demo_store()
    actor = _actor()
    imported = import_skill(store, actor, markdown=_MARKDOWN)
    version = uuid.uuid4()
    store.versions[version] = {
        "id": version,
        "definition": {
            "instructions": "Help.",
            "skills": ["weekly-status"],
            "knowledge": {"collections": ["missing"]},
        },
    }
    run = {
        "id": uuid.uuid4(),
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "agent_version_id": version,
        "conversation_id": uuid.uuid4(),
        "prompt_messages": [{"role": "user", "content": "earlier"}],
    }
    assert has_grounding(store.versions[version]["definition"])
    asyncio.run(ground_run(store, run, "Write the weekly status note"))
    assert run["loaded_skill"]["slug"] == "weekly-status"
    # M39-T05: the match hints at the skill; the model loads the body with skills.load.
    prompt = str(run["prompt_messages"][0]["content"])
    assert "skills.load" in prompt
    assert "STATUS-OK" not in prompt
    cards = citation_parts(
        {
            "hits": [
                {
                    "title": "Dock",
                    "snippet": "ND-1844-QUILL",
                    "anchor": "p1",
                    "page": 1,
                    "library_document_id": "lib",
                },
                "skip",
            ]
        }
    )
    assert cards[0]["type"] == "citation_ref"
    opened = opening_messages({"prompt_messages": []}, {"instructions": "Help."}, "Hi")
    assert [item["role"] for item in opened] == ["system", "user"]
    asyncio.run(ground_run(store, {"id": uuid.uuid4()}, "Hello"))
    assert imported["slug"] == "weekly-status"

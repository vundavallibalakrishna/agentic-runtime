"""HTTP embedding, rerank and portable skill archives."""

from __future__ import annotations

import asyncio
import io
import uuid
import zipfile

import httpx
import pytest
import respx

from ar_common.errors import ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.live_embed import (
    DEFAULT_RERANK_MODEL,
    EmbeddingUnconfiguredError,
    collection_embedding,
    embed_for_collection,
    embed_live,
    load_provider_keys,
    rerank_live,
    resolve_embedding,
)
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


def _provider(store: ChatService, *, base: str = "https://embed.example/v1") -> uuid.UUID:
    provider_id = uuid.uuid4()
    store.providers[provider_id] = {
        "id": provider_id,
        "tenant_id": demo_id("tenant"),
        "kind": "openai_compatible",
        "base_url": base,
        "api_key": "test-key",
    }
    return provider_id


def test_embed_live_reads_provider_batches() -> None:
    store = demo_store()
    _provider(store)
    body = {
        "data": [
            {"index": 0, "embedding": [0.2, 0.4]},
            {"index": 1, "embedding": [1, 2]},
            {"index": 9, "embedding": [0]},
            "skip",
        ]
    }
    with respx.mock:
        respx.post("https://embed.example/v1/embeddings").mock(
            return_value=httpx.Response(200, json=body)
        )
        vectors = embed_live(
            store, demo_id("tenant"), ["north", "south"], model="BAAI/bge-m3", dimensions=2
        )
    assert vectors == [[0.2, 0.4], [1.0, 2.0]]
    assert embed_live(store, demo_id("tenant"), [], model="BAAI/bge-m3", dimensions=2) == []
    store.embed_client = lambda rows: [[0.0]]
    with pytest.raises(EmbeddingUnconfiguredError):
        embed_live(store, demo_id("tenant"), ["north", "south"], model="BAAI/bge-m3", dimensions=2)


def test_embed_live_reports_a_provider_failure() -> None:
    store = demo_store()
    _provider(store)
    with respx.mock:
        respx.post("https://embed.example/v1/embeddings").mock(return_value=httpx.Response(503))
        with pytest.raises(EmbeddingUnconfiguredError):
            embed_live(store, demo_id("tenant"), ["north"], model="BAAI/bge-m3", dimensions=2)
    with respx.mock:
        respx.post("https://embed.example/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        with pytest.raises(EmbeddingUnconfiguredError):
            embed_live(store, demo_id("tenant"), ["north"], model="BAAI/bge-m3", dimensions=2)


def test_rerank_uses_the_inference_endpoint_and_falls_back() -> None:
    store = demo_store()
    provider_id = _provider(store, base="https://api.example/v1/openai")
    model_id = uuid.uuid4()
    store.models[model_id] = {
        "id": model_id,
        "kind": "rerank",
        "upstream_model": "BAAI/bge-reranker-custom",
        "provider_id": provider_id,
    }
    target = resolve_embedding(store, demo_id("tenant"))
    assert target is not None
    assert target.rerank_model == "BAAI/bge-reranker-custom"
    with respx.mock:
        respx.post("https://api.example/v1/openai/rerank").mock(return_value=httpx.Response(404))
        respx.post("https://api.example/v1/inference/BAAI/bge-reranker-custom").mock(
            return_value=httpx.Response(200, json={"scores": [[-2.0, 2.0]]})
        )
        scores = rerank_live(
            store,
            demo_id("tenant"),
            "dock code",
            ["north dock", "other"],
            model=DEFAULT_RERANK_MODEL,
        )
    assert len(scores) == 2
    assert 0.0 < scores[0] < 0.5 < scores[1] < 1.0
    with respx.mock:
        respx.post("https://api.example/v1/openai/rerank").mock(return_value=httpx.Response(500))
        lexical = rerank_live(store, demo_id("tenant"), "dock", ["dock"], model="rerank")
    assert lexical
    store.rerank_client = lambda _query, docs: [0.5 for _item in docs]
    assert rerank_live(store, demo_id("tenant"), "q", ["a"], model="BAAI/bge-m3") == [0.5]
    assert rerank_live(store, demo_id("tenant"), "q", [], model="BAAI/bge-m3") == []


def test_collection_embedding_prefers_a_stored_real_model() -> None:
    model, dims = collection_embedding(
        {"embedding_model": "fake-embed", "embedding_alias": "embed", "chunking": {"dims": 384}}
    )
    assert model == "fake-embed"
    assert dims == 384
    model, dims = collection_embedding(
        {
            "embedding_model": "",
            "embedding_alias": "embed",
            "chunking": {"embedding_model": "BAAI/bge-m3", "dims": "nope"},
        }
    )
    assert model == "BAAI/bge-m3"
    assert dims == 1024
    store = demo_store()
    provider_id = _provider(store)
    store.models[uuid.uuid4()] = {
        "kind": "embedding",
        "upstream_model": "org/custom-embed",
        "provider_id": provider_id,
        "embedding_dimensions": 768,
    }
    chosen = resolve_embedding(store, demo_id("tenant"))
    assert chosen is not None
    assert chosen.model == "org/custom-embed"
    assert chosen.dims == 768
    vectors = embed_for_collection(
        store, {"embedding_model": "fake-embed", "tenant_id": demo_id("tenant")}, ["dock"]
    )
    assert len(vectors) == 1


def test_load_provider_keys_restores_and_skips_bad_rows() -> None:
    store = demo_store()
    store.durable_engine = object()
    good = uuid.uuid4()
    store.providers[good] = {"id": good, "api_key": ""}
    store.providers["skip"] = {"id": "not-a-uuid"}
    store.providers["kept"] = {"id": uuid.uuid4(), "api_key": "already"}
    store.providers["boom"] = {"id": uuid.uuid4()}

    async def _read(_engine: object, provider_id: uuid.UUID) -> str:
        if provider_id == store.providers["boom"]["id"]:
            raise RuntimeError("locked")
        return "restored-key"

    import ar_domain.models.registry as registry

    original = registry.read_api_key
    registry.read_api_key = _read  # type: ignore[method-assign]
    try:
        asyncio.run(load_provider_keys(store))
    finally:
        registry.read_api_key = original
    assert store.providers[good]["api_key"] == "restored-key"
    assert store.providers["kept"]["api_key"] == "already"
    asyncio.run(load_provider_keys(demo_store()))


def test_text_member_is_unchanged_until_refresh() -> None:
    store = demo_store()
    store.embed_client = lambda texts: [[0.1, 0.2] for _text in texts]
    actor = _actor()
    created = KnowledgeBook(store).create_collection(
        actor,
        {
            "name": "Notes",
            "slug": "notes",
            "description": "Notes",
            "embedding_alias": "fake-embed",
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


def test_rerank_reads_indexed_results() -> None:
    store = demo_store()
    _provider(store)
    with respx.mock:
        respx.post("https://embed.example/v1/rerank").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"index": 1, "relevance_score": 0.2},
                        {"index": 0, "score": 0.8},
                        "skip",
                    ]
                },
            )
        )
        scores = rerank_live(store, demo_id("tenant"), "dock", ["a", "b"], model="BAAI/bge-m3")
    assert scores == [0.8, 0.2]


def test_member_edges_and_connection_redaction() -> None:
    store = demo_store()
    store.embed_client = lambda texts: [[0.1, 0.2] for _text in texts]
    actor = _actor()
    created = KnowledgeBook(store).create_collection(
        actor,
        {"name": "Edges", "slug": "edges", "description": "Edges", "embedding_alias": "fake-embed"},
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
    assert "STATUS-OK" in str(run["prompt_messages"][0]["content"])
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
    assert opening_messages({"prompt_messages": []}, "Help.", "Hi", "guide")[0]["role"] == "system"
    asyncio.run(ground_run(store, {"id": uuid.uuid4()}, "Hello"))
    assert imported["slug"] == "weekly-status"

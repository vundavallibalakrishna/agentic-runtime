"""Embeddings come from the model the tenant set, and from nowhere else (M38b-T07b).

Knowledge and memory embed with the model the ``embed`` alias points at. Without one
they refuse and say where to set it. No model id is built in, no provider is guessed,
and no vector is computed in the product's own process.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

import httpx
import orjson
import pytest
import respx

from ar_common.errors import ArError, ConflictError
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.embedding import collection_model, embed_for_collection
from ar_domain.knowledge.pipeline import raise_embedding_error
from ar_domain.knowledge.retrieval import apply_rerank
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.vectors import MemoryVectors, reembed
from ar_domain.models.embedding import (
    NO_EMBEDDING_MODEL,
    EmbeddingFailedError,
    EmbeddingUnconfiguredError,
    embed,
    embedding_model,
    rerank_model,
)
from ar_testing.demo import demo_store
from ar_testing.demo_tenant import seed_demo_tenant
from ar_testing.stand_in import EMBEDDING_MODEL

TENANT = demo_id("tenant")
BASE = "https://embed.example/v1"
ROOT = Path(__file__).resolve().parents[4]


def _actor() -> Actor:
    return Actor(TENANT, demo_id("admin"), PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))


def _bare_store() -> ChatService:
    """The demo tenant with a chat model and no embedding model, like a new tenant."""
    store = ChatService(allow_loopback=True)
    seed_demo_tenant(store)
    return store


def _register(
    store: ChatService,
    name: str,
    *,
    alias: str | None = "embed",
    kind: str = "embedding",
    dimensions: int | None = None,
    base: str = BASE,
) -> uuid.UUID:
    """Register a model the way an administrator does, and point the tenant's alias at it."""
    provider = store.create_provider(
        TENANT, f"provider-{name}", "openai_compatible", base, platform=False, api_key="k-1"
    )
    model = store.create_model(
        TENANT,
        uuid.UUID(str(provider["id"])),
        name,
        name,
        kind,
        platform=False,
        embedding_dimensions=dimensions,
    )
    model_id = uuid.UUID(str(model["id"]))
    if alias is None:
        return model_id
    own = next(
        (
            row
            for row in store.aliases.values()
            if row.get("tenant_id") == TENANT and row.get("alias") == alias
        ),
        None,
    )
    if own is None:
        store.create_alias(TENANT, alias, kind, model_id, platform=False)
    else:
        store.update_alias(TENANT, uuid.UUID(str(own["id"])), model_id, platform=False)
    return model_id


def _vectors(count: int, size: int = 1024, value: float = 0.5) -> dict[str, object]:
    return {"data": [{"index": i, "embedding": [value] * size} for i in range(count)]}


def _answer(size: int = 1024, value: float = 0.5) -> object:
    def reply(request: httpx.Request) -> httpx.Response:
        asked = orjson.loads(request.content)["input"]
        return httpx.Response(200, json=_vectors(len(asked), size, value))

    return reply


def test_a_tenant_without_an_embedding_model_is_told_where_to_set_one() -> None:
    store = _bare_store()
    # A provider with a key is not an embedding model: nothing is guessed from it.
    store.create_provider(TENANT, "chat only", "openai_compatible", BASE, platform=False)
    with pytest.raises(EmbeddingUnconfiguredError) as refused:
        KnowledgeBook(store).create_collection(_actor(), {"slug": "notes", "name": "Notes"})
    assert refused.value.detail == NO_EMBEDDING_MODEL
    assert "Models screen" in refused.value.detail
    assert refused.value.status == 409
    assert store.knowledge_collections == {}
    with pytest.raises(EmbeddingUnconfiguredError):
        MemoryBook(store).create_user(_actor(), {"content": "Prefers short answers"})
    assert store.memory_facts == {}


def test_the_alias_decides_the_model() -> None:
    store = demo_store()
    assert embedding_model(store, TENANT).name == EMBEDDING_MODEL
    own = _register(store, "tenant-embed")
    assert embedding_model(store, TENANT).model_id == own
    # Another tenant still gets the alias that belongs to no tenant.
    assert embedding_model(store, uuid.uuid4()).name == EMBEDDING_MODEL
    # An alias of another name is a separate choice.
    other = _register(store, "wide-embed", alias="embed-wide")
    assert embedding_model(store, TENANT, "embed-wide").model_id == other
    with pytest.raises(EmbeddingUnconfiguredError):
        embedding_model(store, TENANT, "nobody-set-this")


def test_an_alias_that_points_at_a_chat_model_or_a_disabled_provider_is_not_used() -> None:
    store = _bare_store()
    chat = _register(store, "chatty", alias=None, kind="chat")
    alias_id = uuid.uuid4()
    store.aliases[alias_id] = store._alias(alias_id, TENANT, "embed", "embedding", chat)
    with pytest.raises(EmbeddingUnconfiguredError):
        embedding_model(store, TENANT)
    model_id = _register(store, "real-embed")
    assert embedding_model(store, TENANT).model_id == model_id
    provider_id = store.models[model_id]["provider_id"]
    store.providers[provider_id]["status"] = "disabled"
    with pytest.raises(EmbeddingUnconfiguredError):
        embedding_model(store, TENANT)


def test_the_call_goes_to_the_models_provider_in_batches() -> None:
    store = _bare_store()
    _register(store, "vendor/embed-1")
    target = embedding_model(store, TENANT)
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=4))
        vectors = embed(target, [f"text {index}" for index in range(40)])
    assert len(vectors) == 40
    assert route.call_count == 2
    sent = orjson.loads(route.calls[0].request.content)
    assert sent["model"] == "vendor/embed-1"
    assert len(sent["input"]) == 32
    # The model's own vector length is taken unless the administrator set one.
    assert "dimensions" not in sent
    assert route.calls[0].request.headers["authorization"] == "Bearer k-1"


def test_the_vector_length_is_asked_for_only_when_it_is_set() -> None:
    store = _bare_store()
    _register(store, "short-embed", dimensions=256)
    target = embedding_model(store, TENANT)
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=256))
        embed(target, ["one"])
        embed(target, ["one"], dimensions=128)
    assert orjson.loads(route.calls[0].request.content)["dimensions"] == 256
    assert orjson.loads(route.calls[1].request.content)["dimensions"] == 128
    with pytest.raises(ArError, match="Only a model of kind embedding"):
        _register(store, "chat-with-size", alias=None, kind="chat", dimensions=8)


def test_a_provider_failure_is_reported_and_never_replaced_by_a_made_up_vector() -> None:
    store = _bare_store()
    _register(store, "flaky-embed")
    target = embedding_model(store, TENANT)
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(return_value=httpx.Response(500))
        with pytest.raises(EmbeddingFailedError, match="flaky-embed refused the request"):
            embed(target, ["one"])
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=httpx.ConnectError("down"))
        with pytest.raises(EmbeddingFailedError, match="did not answer"):
            embed(target, ["one"])
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(return_value=httpx.Response(200, json=_vectors(1)))
        with pytest.raises(EmbeddingFailedError, match="returned 1 vectors for 2 texts"):
            embed(target, ["one", "two"])
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=8))
        with pytest.raises(EmbeddingUnconfiguredError, match="8 numbers and this needs 1024"):
            embed(target, ["one"], size=1024)


def test_a_collection_records_the_model_that_indexed_it_and_keeps_using_it() -> None:
    store = _bare_store()
    first = _register(store, "embed-a")
    book = KnowledgeBook(store)
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=1024))
        created = book.create_collection(_actor(), {"slug": "notes", "name": "Notes"})
    row = store.knowledge_collections[uuid.UUID(str(created["id"]))]
    assert created["embedding_model"] == "embed-a"
    assert created["dims"] == 1024
    assert row["embedding_model_id"] == first
    assert row["embedding_alias"] == "embed"
    # The alias moves on. The collection's vectors still belong to the first model.
    _register(store, "embed-b", base="https://other.example/v1")
    assert embedding_model(store, TENANT).name == "embed-b"
    assert collection_model(store, row).name == "embed-a"
    with respx.mock:
        used = respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=1024))
        embed_for_collection(store, row, ["a question"])
    assert used.call_count == 1
    # The model cannot be removed from under the collection.
    for alias in [a for a in store.aliases.values() if a.get("primary_model_id") == first]:
        del store.aliases[alias["id"]]
    with pytest.raises(ConflictError, match="Notes"):
        store.delete_model(TENANT, first, platform=False)
    # A model that is gone anyway is a refusal that says what to do, not another model.
    del store.models[first]
    with pytest.raises(EmbeddingUnconfiguredError, match=r"embed-a.*re-index"):
        embed_for_collection(store, row, ["a question"])


def test_a_collection_is_not_created_against_a_model_of_an_unsupported_length() -> None:
    store = _bare_store()
    _register(store, "odd-embed")
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=77))
        with pytest.raises(ArError, match=r"unsupported_embedding_dims.*77"):
            KnowledgeBook(store).create_collection(_actor(), {"slug": "odd", "name": "Odd"})
    assert store.knowledge_collections == {}


def test_reindexing_with_an_alias_moves_the_collection_to_that_alias_model() -> None:
    store = demo_store()
    book = KnowledgeBook(store)
    created = book.create_collection(_actor(), {"slug": "moves", "name": "Moves"})
    collection_id = uuid.UUID(str(created["id"]))
    row = store.knowledge_collections[collection_id]
    assert row["embedding_model"] == EMBEDDING_MODEL
    second = _register(store, "embed-next", alias="embed-next")
    with respx.mock:
        respx.route(host="127.0.0.1").pass_through()
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=1024))
        book.reindex_collection(_actor(), collection_id, {"embedding_alias": "embed-next"})
    assert row["embedding_model"] == "embed-next"
    assert row["embedding_model_id"] == second
    assert row["embedding_alias"] == "embed-next"


def test_a_search_embeds_the_question_once_for_each_indexing_model() -> None:
    store = demo_store()
    book = KnowledgeBook(store)
    actor = _actor()
    one = book.create_collection(actor, {"slug": "one", "name": "One"})
    _register(store, "embed-two")
    with respx.mock:
        respx.route(host="127.0.0.1").pass_through()
        other = respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=1024))
        two = book.create_collection(actor, {"slug": "two", "name": "Two"})
        before = other.call_count
        found = book.search(
            actor,
            {
                "query": "where is the visitor desk",
                "collection_ids": [uuid.UUID(str(one["id"])), uuid.UUID(str(two["id"]))],
            },
        )
        assert other.call_count == before + 1
    assert found["hits"] == []


def test_a_document_that_cannot_be_embedded_says_why() -> None:
    store = demo_store()
    book = KnowledgeBook(store)
    actor = _actor()
    created = book.create_collection(actor, {"slug": "docs", "name": "Docs"})
    row = store.knowledge_collections[uuid.UUID(str(created["id"]))]
    model_id = row["embedding_model_id"]
    saved = dict(store.models[model_id])
    del store.models[model_id]
    uploaded = store.upload(
        TENANT, actor.user_id, "desk.md", "text/markdown", b"# Desk\n\nThe desk opens at 08:30."
    )
    with pytest.raises(EmbeddingUnconfiguredError):
        asyncio.run(
            book.add_documents(actor, uuid.UUID(str(created["id"])), {"file_ids": [uploaded["id"]]})
        )
    document = next(iter(store.knowledge_documents.values()))
    assert document["status"] == "failed"
    assert str(document["error"]).startswith("embedding_unconfigured: ")
    # What the worker wrote on the document is the error the uploader is given.
    with pytest.raises(EmbeddingUnconfiguredError, match="re-index"):
        raise_embedding_error(document)
    raise_embedding_error({"error": "unsupported_format"})
    store.models[model_id] = saved


def test_a_fact_records_its_model_and_is_compared_only_with_that_models_vectors() -> None:
    store = demo_store()
    actor = _actor()
    book = MemoryBook(store)
    fact = book.create_user(actor, {"content": "The office closes at noon on Fridays"})
    row = store.memory_facts[uuid.UUID(str(fact["id"]))]
    first = embedding_model(store, TENANT).model_id
    assert row["embedding_model_id"] == first
    assert len(row["embedding"]) == 1024
    assert MemoryVectors(store, TENANT).of(row) == row["embedding"]
    # The tenant changes its embedding model.
    second = _register(store, "embed-new")
    vectors = MemoryVectors(store, TENANT)
    assert vectors.of(row) == []
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(value=0.25))
        # The old fact is still found by the words it shares with the question.
        found = book.list_user(actor, query="when does the office close on Fridays")
        assert [item["id"] for item in found] == [fact["id"]]
        assert reembed(store, TENANT) == 1
        assert reembed(store, TENANT) == 0
    assert row["embedding_model_id"] == second
    assert row["embedding"] == [0.25] * 1024


def test_memory_without_a_model_refuses_to_save_and_still_reads_by_words() -> None:
    store = demo_store()
    actor = _actor()
    book = MemoryBook(store)
    fact = book.create_user(actor, {"content": "Prefers the metric system"})
    for alias_id in [key for key, row in store.aliases.items() if row.get("alias") == "embed"]:
        del store.aliases[alias_id]
    with pytest.raises(EmbeddingUnconfiguredError, match="Models screen"):
        book.create_user(actor, {"content": "Lives in Pune"})
    with pytest.raises(EmbeddingUnconfiguredError):
        book.patch_user(actor, uuid.UUID(str(fact["id"])), {"content": "Prefers imperial"})
    assert store.memory_facts[uuid.UUID(str(fact["id"]))]["content"] == "Prefers the metric system"
    found = book.list_user(actor, query="which system is preferred, metric")
    assert [item["id"] for item in found] == [fact["id"]]
    # A turn is not failed because nothing can be remembered from it.
    run = {"id": uuid.uuid4(), "tenant_id": TENANT, "user_id": actor.user_id}
    ops = [{"op": "add", "content": "Works night shifts", "confidence": 0.9, "category": "fact"}]
    assert book.apply_ops(actor, run, ops) == []


def test_a_memory_model_of_the_wrong_length_is_refused_with_the_fix() -> None:
    store = _bare_store()
    _register(store, "wide-embed")
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(size=3072))
        with pytest.raises(EmbeddingUnconfiguredError, match="3072 numbers and this needs 1024"):
            MemoryBook(store).create_user(_actor(), {"content": "Prefers short answers"})


def test_passages_are_scored_by_a_rerank_model_or_not_at_all() -> None:
    hits = [
        {"snippet": "parking is free", "chunk_id": "b", "score": 0.03},
        {"snippet": "desk opens at nine", "chunk_id": "a", "score": 0.02},
    ]
    store = _bare_store()
    assert rerank_model(store, TENANT) is None
    # No rerank model: the passages keep the order the search found them, unscored.
    kept, _ms, warning, scored = apply_rerank("desk opens", hits, top_k=2)
    assert [hit["chunk_id"] for hit in kept] == ["b", "a"]
    assert (warning, scored) == (None, False)
    assert all("rerank_score" not in hit for hit in kept)
    _register(store, "vendor/rerank-1", alias="rerank", kind="rerank")
    target = rerank_model(store, TENANT)
    assert target is not None
    scores = {"results": [{"index": 0, "relevance_score": 0.1}, {"index": 1, "score": 0.9}]}
    with respx.mock:
        route = respx.post(f"{BASE}/rerank").mock(return_value=httpx.Response(200, json=scores))
        kept, _ms, warning, scored = apply_rerank("desk opens", hits, top_k=2, target=target)
    assert [hit["chunk_id"] for hit in kept] == ["a"]
    assert (warning, scored) == (None, True)
    assert orjson.loads(route.calls[0].request.content)["model"] == "vendor/rerank-1"
    # A rerank model that fails is a warning, and the passages stay in search order.
    with respx.mock:
        respx.post(f"{BASE}/rerank").mock(return_value=httpx.Response(503))
        kept, _ms, warning, scored = apply_rerank("desk opens", hits, top_k=2, target=target)
    assert [hit["chunk_id"] for hit in kept] == ["b", "a"]
    assert (warning, scored) == ("rerank_unavailable", False)


def test_a_search_without_a_rerank_model_returns_the_closest_passages_unjudged() -> None:
    store = demo_store()
    for alias_id in [key for key, row in store.aliases.items() if row.get("alias") == "rerank"]:
        del store.aliases[alias_id]
    actor = _actor()
    book = KnowledgeBook(store)
    created = book.create_collection(actor, {"slug": "desk", "name": "Desk"})
    collection_id = uuid.UUID(str(created["id"]))
    uploaded = store.upload(
        TENANT, actor.user_id, "desk.md", "text/markdown", b"# Desk\n\nReception opens at 08:30."
    )
    asyncio.run(book.add_documents(actor, collection_id, {"file_ids": [uploaded["id"]]}))
    # The question shares no word with the passage. It is still the closest passage.
    found = book.search(actor, {"query": "morning hours", "collection_ids": [collection_id]})
    assert len(found["hits"]) == 1
    assert found["scored"] is False
    assert found["answerable"] is True
    assert found["rerank_model"] == ""
    assert "rerank_score" not in found["hits"][0]


def test_a_conversation_cannot_be_pointed_at_an_embedding_alias() -> None:
    store = demo_store()
    user = demo_id("admin")
    with pytest.raises(ArError, match="A conversation needs a chat alias"):
        store.create_conversation(TENANT, user, None, model_alias="embed")
    made = store.create_conversation(TENANT, user, None, model_alias="fast")
    assert made["model_alias"] == "fast"
    with pytest.raises(ArError, match="rerank"):
        store.patch_conversation(
            TENANT,
            user,
            uuid.UUID(str(made["id"])),
            title=None,
            pinned=None,
            model_alias="rerank",
            model_alias_set=True,
        )
    assert store.conversations[uuid.UUID(str(made["id"]))]["model_alias"] == "fast"


def test_no_product_code_names_an_embedding_model_or_makes_a_vector_itself() -> None:
    """The built-in model id, the provider guess and the in-process vectors stay gone."""
    banned = (
        "BAAI/",
        "bge-m3",
        "fake-embed",
        "fake-rerank",
        "unit_vector",
        "embed_client",
        "rerank_client",
        "DEFAULT_EMBEDDING_MODEL",
    )
    # The dev seed still writes the scripted provider's rows (M38b-T06), and the scripted
    # model server is where the stand-in vectors are made.
    allowed = {
        ROOT / "libs/ar_domain/src/ar_domain/seed/m2.py",
        ROOT / "libs/ar_common/src/ar_common/vectors.py",
    }
    roots = [ROOT / "libs/ar_domain/src", ROOT / "libs/ar_common/src"]
    roots += [path / "src" for path in (ROOT / "services").iterdir() if path.name != "fake_llm"]
    found: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path in allowed:
                continue
            text = path.read_text(encoding="utf-8")
            found += [f"{path.relative_to(ROOT)}: {word}" for word in banned if word in text]
    assert found == []


def test_no_test_replaces_a_clock_function_for_every_thread() -> None:
    """The stand-in model server runs on a thread of the test process.

    A test that replaces ``asyncio.sleep``, ``asyncio.wait_for`` or ``time.sleep`` replaces
    it for that thread too, and can stop the server or make its idle loop spin. Such a
    replacement goes through ``ar_testing.sleeping.in_this_thread``.
    """
    replaced = re.compile(
        r"setattr\([^#\n]*(asyncio[^,\n]*,\s*\"(sleep|wait_for)\"|asyncio\.(sleep|wait_for)\""
        r"|time[^,\n]*,\s*\"sleep\"|time\.sleep\")"
    )
    roots = [ROOT / "libs", ROOT / "services", ROOT / "connectors", ROOT / "tests"]
    found: list[str] = []
    for root in roots:
        for path in root.rglob("test_*.py"):
            if ".venv" in path.parts or path == Path(__file__).resolve():
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if replaced.search(line) and "in_this_thread(" not in line:
                    found.append(f"{path.relative_to(ROOT)}:{number}")
    assert found == []


# --- M38b-T07d: the rerank route is the model's setting, closeness is shown, memory re-embeds


def test_the_rerank_route_is_the_models_own_setting() -> None:
    from ar_domain.models.embedding import (
        DEFAULT_RERANK_FLOOR,
        ModelTarget,
        rerank_floor,
        rerank_route,
    )

    def target(options: dict[str, object] | None = None) -> ModelTarget:
        return ModelTarget(
            model_id=uuid.uuid4(),
            name="vendor/rerank-1",
            label="Rerank",
            base_url=BASE,
            api_key="k-1",
            timeout_s=5.0,
            dimensions=None,
            request_options=options or {},
        )

    # Nothing set: a ``/rerank`` path under the provider's address, the usual body.
    assert rerank_route(target()) == (f"{BASE}/rerank", "query")
    # A path of the customer's choosing, with or without its slash.
    assert rerank_route(target({"rerank": {"path": "v2/score"}})) == (f"{BASE}/v2/score", "query")
    assert rerank_route(target({"rerank": {"path": "/v2/score"}})) == (f"{BASE}/v2/score", "query")
    # A whole address, when the rerank endpoint lives elsewhere than the provider.
    elsewhere = {"rerank": {"path": "https://score.example/run", "body": "queries"}}
    assert rerank_route(target(elsewhere)) == ("https://score.example/run", "queries")
    # The body shape is one of the two; anything else is the usual one.
    assert rerank_route(target({"rerank": {"body": "queries"}}))[1] == "queries"
    assert rerank_route(target({"rerank": {"body": "odd"}}))[1] == "query"
    assert rerank_route(target({"rerank": "not a section"})) == (f"{BASE}/rerank", "query")
    # The bar a passage's score must clear is the model's too; unset, the product's default.
    assert rerank_floor(None) == DEFAULT_RERANK_FLOOR == 0.2
    assert rerank_floor(target()) == 0.2
    assert rerank_floor(target({"rerank": {"min_score": 0.02}})) == 0.02
    assert rerank_floor(target({"rerank": {"min_score": 0}})) == 0.0
    assert rerank_floor(target({"rerank": {"min_score": 7}})) == 0.2
    assert rerank_floor(target({"rerank": {"min_score": "low"}})) == 0.2


def test_a_rerank_model_is_called_on_the_route_it_is_registered_with() -> None:
    from ar_domain.models.embedding import rerank

    store = demo_store()
    model_id = _register(store, "vendor/rerank-2", alias="rerank", kind="rerank")
    store.update_model(
        TENANT,
        model_id,
        platform=False,
        request_options={"rerank": {"path": "/inference/vendor/rerank-2", "body": "queries"}},
    )
    target = rerank_model(store, TENANT)
    assert target is not None
    with respx.mock:
        route = respx.post(f"{BASE}/inference/vendor/rerank-2").mock(
            return_value=httpx.Response(200, json={"scores": [0.9, 0.1]})
        )
        scores = rerank(target, "desk opens", ["Reception opens at 08:30.", "Lunch is at noon."])
    assert scores == [0.9, 0.1]
    body = orjson.loads(route.calls[0].request.content)
    assert body == {
        "queries": ["desk opens"],
        "documents": ["Reception opens at 08:30.", "Lunch is at noon."],
    }


def test_fused_passages_carry_how_close_they_are_to_the_question() -> None:
    from ar_domain.knowledge.store import rrf_fuse

    a, b, c = (str(uuid.uuid4()) for _ in range(3))
    rows = {key: (str(uuid.uuid4()), str(uuid.uuid4())) for key in (a, b, c)}
    fused = rrf_fuse([(a, 1, 0.91), (b, 2, 0.72)], [(c, 1)], rows, rrf_k=60, fused_k=10)
    by_id = {str(chunk.chunk_id): chunk for chunk in fused}
    assert by_id[a].similarity == pytest.approx(0.91)
    assert by_id[b].similarity == pytest.approx(0.72)
    # A passage found only by its words has no similarity to report.
    assert by_id[c].similarity is None
    # Dense entries without a similarity still fuse as before.
    plain = rrf_fuse([(a, 1)], [(c, 1)], rows, rrf_k=60, fused_k=10)
    assert all(chunk.similarity is None for chunk in plain)


def test_an_unscored_search_says_how_close_each_passage_is() -> None:
    store = demo_store()
    for alias_id in [key for key, row in store.aliases.items() if row.get("alias") == "rerank"]:
        del store.aliases[alias_id]
    actor = _actor()
    book = KnowledgeBook(store)
    created = book.create_collection(actor, {"slug": "desk", "name": "Desk"})
    collection_id = uuid.UUID(str(created["id"]))
    uploaded = store.upload(
        TENANT, actor.user_id, "desk.md", "text/markdown", b"# Desk\n\nReception opens at 08:30."
    )
    asyncio.run(book.add_documents(actor, collection_id, {"file_ids": [uploaded["id"]]}))
    found = book.search(actor, {"query": "morning hours", "collection_ids": [collection_id]})
    assert found["scored"] is False
    hit = found["hits"][0]
    assert isinstance(hit["similarity"], float)
    assert -1.0 <= hit["similarity"] <= 1.0


def test_memory_embeds_its_facts_again_by_itself_after_the_embedding_model_changes() -> None:
    store = demo_store()
    actor = _actor()
    book = MemoryBook(store)
    fact = book.create_user(actor, {"content": "The office closes at noon on Fridays"})
    row = store.memory_facts[uuid.UUID(str(fact["id"]))]
    first = row["embedding_model_id"]
    # Outside a request (a script), the alias change embeds the facts here and now.
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(value=0.25))
        second = _register(store, "embed-new")
    assert second != first
    assert row["embedding_model_id"] == second
    assert row["embedding"] == [0.25] * 1024
    assert MemoryVectors(store, TENANT).of(row) == row["embedding"]

    # Inside a request, the work runs beside it on the loop and finishes on its own.
    async def change() -> None:
        with respx.mock:
            respx.post(f"{BASE}/embeddings").mock(side_effect=_answer(value=0.75))
            third = _register(store, "embed-newer")
            assert row["embedding_model_id"] == second  # not yet: the request returns first
            await asyncio.gather(*store.tasks)
        assert row["embedding_model_id"] == third
        assert row["embedding"] == [0.75] * 1024

    asyncio.run(change())


def test_a_dead_embedding_model_does_not_undo_the_alias_change() -> None:
    store = demo_store()
    actor = _actor()
    book = MemoryBook(store)
    fact = book.create_user(actor, {"content": "Prefers the metric system"})
    row = store.memory_facts[uuid.UUID(str(fact["id"]))]
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(return_value=httpx.Response(503))
        new = _register(store, "embed-down")
    # The alias points at the new model; the fact keeps its old vector and is found by words.
    assert embedding_model(store, TENANT).model_id == new
    assert row["embedding_model_id"] != new
    assert MemoryVectors(store, TENANT).of(row) == []
    found = book.list_user(actor, query="which system is preferred, metric")
    assert [item["id"] for item in found] == [fact["id"]]


def test_a_passage_counts_when_it_clears_the_rerank_models_own_bar() -> None:
    """Each rerank model scores on its own scale, so the bar is the model's setting."""
    from ar_contracts.definitions import KnowledgeSpec

    store = demo_store()
    model_id = _register(store, "vendor/rerank-3", alias="rerank", kind="rerank")
    hits = [
        {"chunk_id": "a", "snippet": "Sick leave is paid in full."},
        {"chunk_id": "b", "snippet": "Meals are covered up to 45 euros."},
    ]
    scores = {"scores": [0.06, 0.001]}  # a model whose scores sit low on its scale
    with respx.mock:
        respx.post(f"{BASE}/rerank").mock(return_value=httpx.Response(200, json=scores))
        # At the product's default bar nothing counts, and the search says so.
        kept, _ms, _warning, scored = apply_rerank(
            "sick pay", hits, top_k=5, target=rerank_model(store, TENANT)
        )
        assert (kept, scored) == ([], True)
        # The administrator sets the model's bar, and the right passage counts.
        store.update_model(
            TENANT, model_id, platform=False, request_options={"rerank": {"min_score": 0.02}}
        )
        kept, _ms, _warning, scored = apply_rerank(
            "sick pay", hits, top_k=5, target=rerank_model(store, TENANT)
        )
        assert [hit["chunk_id"] for hit in kept] == ["a"]
        # A caller with a bar of its own, such as an agent definition, uses that instead.
        kept, _ms, _warning, scored = apply_rerank(
            "sick pay", hits, top_k=5, min_score=0.0, target=rerank_model(store, TENANT)
        )
        assert [hit["chunk_id"] for hit in kept] == ["a", "b"]
    # An agent definition leaves the bar to the model unless it says otherwise.
    assert KnowledgeSpec().min_score is None
    assert KnowledgeSpec(min_score=0.5).min_score == 0.5

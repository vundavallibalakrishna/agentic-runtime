"""Tools are ranked by meaning and by shared words, never by a made-up vector (M38a-T06).

An agent with many tools is offered the ones closest to the request, and ``control.search``
finds a tool by description. The ranking used vectors computed from a hash of the text,
which carry no meaning: which tools the model saw was close to random.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import orjson
import respx

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.search import (
    BY_MEANING,
    BY_WORDS,
    prepare_tools,
    rank_tools,
    tool_text,
    word_overlap,
)
from ar_testing.demo import demo_store

TENANT = demo_id("tenant")
BASE = "https://embed.example/v1"
ROOT = Path(__file__).resolve().parents[4]

TOOLS = [
    {"qualified_name": "mail.send", "description": "Send an email message to a recipient."},
    {"qualified_name": "files.read", "description": "Read the contents of a stored file."},
    {"qualified_name": "sheets.total", "description": "Add up a column of a spreadsheet."},
]


def _bare() -> ChatService:
    """A tenant with a chat model and no embedding model."""
    store = ChatService(allow_loopback=True)
    store.seed_demo_tenant()
    return store


def _with_embeddings(store: ChatService) -> None:
    provider = store.create_provider(TENANT, "vectors", "openai_compatible", BASE, platform=False)
    model = store.create_model(
        TENANT, uuid.UUID(str(provider["id"])), "embed-1", "embed-1", "embedding", platform=False
    )
    store.create_alias(TENANT, "embed", "embedding", uuid.UUID(str(model["id"])), platform=False)


def _meaning(request: httpx.Request) -> httpx.Response:
    """A provider for which "post a letter" means the same as the mail tool."""
    close = {"post a letter to my landlord", tool_text(TOOLS[0])}
    vectors = [
        [1.0, 0.0] if text in close else [0.0, 1.0]
        for text in orjson.loads(request.content)["input"]
    ]
    data = [{"index": index, "embedding": vector} for index, vector in enumerate(vectors)]
    return httpx.Response(200, json={"data": data})


def test_words_are_counted_whatever_the_punctuation() -> None:
    assert tool_text(TOOLS[0]) == "mail.send: Send an email message to a recipient."
    assert word_overlap("Send an EMAIL!", tool_text(TOOLS[0])) == 1.0
    assert word_overlap("read file", tool_text(TOOLS[1])) == 1.0
    assert word_overlap("launch rocket", tool_text(TOOLS[1])) == 0.0
    assert word_overlap("", tool_text(TOOLS[1])) == 0.0
    # A word is whole in any script: an accented letter does not split it.
    assert word_overlap("Météo À PARIS", "paris.météo: la météo à Paris") == 1.0
    assert word_overlap("mto", "paris.météo: la météo à Paris") == 0.0


def test_without_an_embedding_model_the_ranking_is_by_words_and_says_so() -> None:
    ranked, how = rank_tools(_bare(), TENANT, "total the spreadsheet column", list(TOOLS))
    assert how == BY_WORDS
    assert ranked[0][1]["qualified_name"] == "sheets.total"
    # A request that shares no word with any tool ranks none above another.
    ranked, _how = rank_tools(_bare(), TENANT, "launch rocket", list(TOOLS))
    assert {score for score, _tool in ranked} == {0.0}


def _settled(store: ChatService) -> None:
    """Wait for the thread that embeds the catalogue."""
    worker = store.tool_vectors.worker
    assert worker is not None, "no catalogue embedding was started"
    worker.join(timeout=10)
    assert not worker.is_alive()


def _inputs(route: respx.Route) -> list[list[str]]:
    return [orjson.loads(call.request.content)["input"] for call in route.calls]


def test_with_an_embedding_model_a_tool_is_found_by_what_it_means() -> None:
    store = _bare()
    _with_embeddings(store)
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings").mock(side_effect=_meaning)
        assert prepare_tools(store, TENANT, list(TOOLS), wait=True) is True
        ranked, how = rank_tools(store, TENANT, "post a letter to my landlord", list(TOOLS))
        assert how == BY_MEANING
        # No word of the request is in the mail tool's text. Its meaning is.
        assert word_overlap("post a letter to my landlord", tool_text(TOOLS[0])) < 0.5
        assert ranked[0][1]["qualified_name"] == "mail.send"
        assert ranked[0][0] > ranked[1][0]
        # The catalogue is embedded once. A search embeds only the request.
        rank_tools(store, TENANT, "post a letter to my landlord", list(TOOLS))
    assert _inputs(route) == [
        [tool_text(tool) for tool in TOOLS],
        ["post a letter to my landlord"],
        ["post a letter to my landlord"],
    ]


def test_a_search_never_waits_for_the_catalogue_to_be_embedded() -> None:
    """The first search is ranked by words while the vectors are made on their own thread."""
    store = _bare()
    _with_embeddings(store)
    asked = "post a letter to my landlord"
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings").mock(side_effect=_meaning)
        _ranked, how = rank_tools(store, TENANT, asked, list(TOOLS))
        assert how == BY_WORDS, "the search answered before the catalogue was embedded"
        _settled(store)
        ranked, how = rank_tools(store, TENANT, asked, list(TOOLS))
    assert how == BY_MEANING
    assert ranked[0][1]["qualified_name"] == "mail.send"
    # The first search sent nothing itself: one call for the catalogue, one for the request.
    assert _inputs(route) == [[tool_text(tool) for tool in TOOLS], [asked]]


def test_a_tool_whose_description_changes_is_embedded_again() -> None:
    store = _bare()
    _with_embeddings(store)
    changed = [dict(tool) for tool in TOOLS]
    changed[1]["description"] = "Read a stored file, a page at a time."
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings").mock(side_effect=_meaning)
        prepare_tools(store, TENANT, list(TOOLS), wait=True)
        assert prepare_tools(store, TENANT, changed) is False, "one text has no vector yet"
        _settled(store)
        assert prepare_tools(store, TENANT, changed) is True
    assert _inputs(route) == [[tool_text(tool) for tool in TOOLS], [tool_text(changed[1])]]


def test_an_embedding_model_that_does_not_answer_leaves_the_ranking_by_words() -> None:
    store = _bare()
    _with_embeddings(store)
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(return_value=httpx.Response(503))
        rank_tools(store, TENANT, "send an email", list(TOOLS))
        _settled(store)
        ranked, how = rank_tools(store, TENANT, "send an email", list(TOOLS))
        _settled(store)
    assert how == BY_WORDS
    assert ranked[0][1]["qualified_name"] == "mail.send"


def test_a_request_that_cannot_be_embedded_is_ranked_by_words() -> None:
    """The catalogue has its vectors, and the provider stops answering."""
    store = _bare()
    _with_embeddings(store)
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings")
        route.side_effect = [_meaning, httpx.Response(503)]
        prepare_tools(store, TENANT, list(TOOLS), wait=True)
        ranked, how = rank_tools(store, TENANT, "send an email", list(TOOLS))
    assert how == BY_WORDS
    assert ranked[0][1]["qualified_name"] == "mail.send"


def test_without_an_embedding_model_nothing_is_prepared() -> None:
    assert prepare_tools(_bare(), TENANT, list(TOOLS), wait=True) is False


def test_an_agent_with_many_tools_is_offered_as_many_as_its_definition_says() -> None:
    store = demo_store()
    agent = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    version = store.versions[agent["published_version_id"]]
    definition = version["definition"]
    definition["tools"] = [
        {"server": str(row["slug"]), "version": "*", "include": ["*"]}
        for row in store.tool_servers.values()
        if row.get("status") == "approved"
    ]
    pipeline = ToolPipeline(store)
    everything = pipeline.resolve_catalog(agent_version_id=version["id"], user_id=demo_id("admin"))
    assert len(everything["tools"]) > 30
    offered = pipeline.resolve_catalog(
        agent_version_id=version["id"], user_id=demo_id("admin"), query="read a file"
    )
    assert offered["tool_search_active"] is True
    assert len(offered["tools"]) == 12
    assert offered["ranked_by"] in {BY_MEANING, BY_WORDS}
    definition["tool_search"] = {"mode": "auto", "top_k": 6}
    fewer = pipeline.resolve_catalog(
        agent_version_id=version["id"], user_id=demo_id("admin"), query="read a file"
    )
    assert len(fewer["tools"]) == 6
    definition["tool_search"] = {"mode": "auto", "top_k": 400}
    capped = pipeline.resolve_catalog(
        agent_version_id=version["id"], user_id=demo_id("admin"), query="read a file"
    )
    assert len(capped["tools"]) == 32


def test_no_product_code_makes_a_vector_for_a_tool() -> None:
    store = demo_store()
    assert all("embedding" not in row for row in store.tool_versions.values())
    roots = [ROOT / "libs/ar_domain/src", ROOT / "libs/ar_common/src"]
    roots += [path / "src" for path in (ROOT / "services").iterdir() if path.name != "fake_llm"]
    found = [
        str(path.relative_to(ROOT))
        for root in roots
        for path in root.rglob("*.py")
        if "hash_embedding" in path.read_text(encoding="utf-8")
    ]
    assert found == []

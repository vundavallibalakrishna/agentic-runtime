"""Tool-search vectors are durable, so a fresh process ranks by meaning. Task: M39-T04a."""

from __future__ import annotations

import uuid

import httpx
import orjson
import respx

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.tools.search import BY_MEANING, prepare_tools, rank_tools, tool_text
from ar_testing.demo_tenant import seed_demo_tenant

TENANT = demo_id("tenant")
BASE = "https://embed.example/v1"

TOOLS = [
    {"qualified_name": "mail.send", "description": "Send an email message to a recipient."},
    {"qualified_name": "files.read", "description": "Read the contents of a stored file."},
    {"qualified_name": "sheets.total", "description": "Add up a column of a spreadsheet."},
]


def _store() -> ChatService:
    store = ChatService(allow_loopback=True)
    seed_demo_tenant(store)
    provider = store.create_provider(TENANT, "vectors", "openai_compatible", BASE, platform=False)
    model = store.create_model(
        TENANT, uuid.UUID(str(provider["id"])), "embed-1", "embed-1", "embedding", platform=False
    )
    store.create_alias(TENANT, "embed", "embedding", uuid.UUID(str(model["id"])), platform=False)
    return store


def _meaning(request: httpx.Request) -> httpx.Response:
    close = {"post a letter to my landlord", tool_text(TOOLS[0])}
    vectors = [
        [1.0, 0.0] if text in close else [0.0, 1.0]
        for text in orjson.loads(request.content)["input"]
    ]
    return httpx.Response(
        200, json={"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]}
    )


def test_computed_vectors_are_written_to_the_durable_table() -> None:
    store = _store()
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_meaning)
        assert prepare_tools(store, TENANT, list(TOOLS), wait=True) is True
    rows = list(store.tool_search_vectors.values())
    assert len(rows) == len(TOOLS)
    for row in rows:
        assert row["tenant_id"] == TENANT
        assert isinstance(row["vector"], list) and row["vector"]
        assert row["model_id"] and row["text_hash"]


def test_a_fresh_process_does_not_re_embed_and_ranks_by_meaning() -> None:
    store = _store()
    with respx.mock:
        respx.post(f"{BASE}/embeddings").mock(side_effect=_meaning)
        assert prepare_tools(store, TENANT, list(TOOLS), wait=True) is True
    assert store.tool_search_vectors  # the table holds the vectors

    # A restart: the in-memory cache is gone, but the tenant's table was hydrated.
    store.tool_vectors = None  # type: ignore[attr-defined]
    with respx.mock:
        route = respx.post(f"{BASE}/embeddings").mock(side_effect=_meaning)
        assert prepare_tools(store, TENANT, list(TOOLS), wait=True) is True
        # The catalogue was taken from the table, not embedded again.
        assert len(route.calls) == 0
        ranked, how = rank_tools(store, TENANT, "post a letter to my landlord", list(TOOLS))
        assert how == BY_MEANING
        assert ranked[0][1]["qualified_name"] == "mail.send"

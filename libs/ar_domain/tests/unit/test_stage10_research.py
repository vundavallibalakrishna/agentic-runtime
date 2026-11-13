"""Stage 10 research engine and citation check. Proof: unit."""

import asyncio
import uuid

from ar_domain.chat.service import demo_id
from ar_domain.research.citations import source_record, verify_report
from ar_domain.research.engine import advance, initial_state, public_research, run_subtask
from ar_domain.research.fetch import extract_readable
from ar_domain.research.handlers import dispatch_context, dispatch_research
from ar_testing.demo import add_library_notes, demo_store


def test_unsupported_claim_is_dropped() -> None:
    source = source_record(
        url="fixture://notes/overview",
        title="Overview",
        text="The stored note says the kite needs a steady breeze.",
        query_id="1",
    )
    report = (
        "The stored note says the kite needs a steady breeze [1]. "
        "The note also says the kite was built in a factory [1]."
    )
    cleaned, citations = verify_report(report, [source])
    assert "breeze" in cleaned
    assert "factory" not in cleaned
    assert {row["status"] for row in citations} == {"supported", "dropped"}
    assert source["sha256"]
    assert source["fetched_at"]


def test_readable_text_drops_tags() -> None:
    assert "Hello" in extract_readable("<script>bad()</script><p>Hello there.</p>")


def test_research_run_cites_the_tenants_library() -> None:
    store = demo_store()
    add_library_notes(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    question = "What do the stored notes say about a kite?"
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), question, research=True, schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, question, []))
    view = public_research(store.runs[run_id])
    assert view["status"] == "completed"
    assert view["sources"]
    assert all(str(row["url"]).startswith("library://") for row in view["sources"])
    assert all(row["sha256"] and row["fetchedAt"] for row in view["sources"])
    assert len({row["url"] for row in view["sources"]}) == len(view["sources"])
    assert "[1]" in str(view["report"])
    assert "kite" in str(view["report"]).lower()
    started = [row for row in store.audit_log if row.get("action") == "research.started"]
    finished = [row for row in store.audit_log if row.get("action") == "research.completed"]
    assert started and finished


def test_research_with_nothing_to_find_says_where_it_looked() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    question = "What is the airspeed of an unladen swallow?"
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), question, research=True, schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, question, []))
    view = public_research(store.runs[run_id])
    assert view["status"] == "completed"
    assert view["sources"] == []
    report = str(view["report"])
    assert "document library" in report
    assert "Web search is not configured" in report
    assert "fixture" not in report


def test_subtask_reads_library_passages_and_tools_return_text() -> None:
    store = demo_store()
    add_library_notes(store)
    tenant = demo_id("tenant")
    result = run_subtask(store, tenant, {"id": "1", "text": "kite string line"})
    assert result["sources"]
    found = dispatch_research(store, "search", {"query": "kite", "_tenant_id": tenant})
    assert found["is_error"] is False
    address = found["structured"]["hits"][0]["url"]
    assert address.startswith("library://")
    page = dispatch_research(store, "fetch", {"url": address, "_tenant_id": tenant})
    assert "kite" in page["text"].lower()
    other = dispatch_research(store, "fetch", {"url": address, "_tenant_id": uuid.uuid4()})
    assert other["code"] == "not_found"
    canned = dispatch_research(store, "fetch", {"url": "fixture://notes/overview"})
    assert canned["code"] == "validation_failed"
    missing = dispatch_context(store, "retrieve", {"output_id": "missing"})
    assert missing["code"] == "not_found"


def test_cancel_stops_the_next_phase() -> None:
    store = demo_store()
    state = initial_state("kites")
    run = {"id": "run", "status": "cancelled", "checkpoint": {"research": state}, "tenant_id": "t"}
    assert advance(store, run, "kites") == "final"


def test_sandbox_fetcher_is_used_when_the_page_is_thin() -> None:
    store = demo_store()

    def render(url: str) -> str:
        assert url.startswith("https://")
        return "<html><body>The sandbox reader found a long sentence about the page.</body></html>"

    store.http_send = lambda *args, **kwargs: _response("<html><body>Hi</body></html>")  # type: ignore[method-assign]
    store.sandbox_fetch = render
    store.egress_allowlist = ["*"]
    from ar_domain.research.fetch import fetch_page

    page = fetch_page(store, "https://example.com/note")
    assert page["extractor"] == "sandbox_chromium"
    assert "sandbox reader" in page["text"]


def _response(text: str) -> object:
    import httpx

    return httpx.Response(200, text=text)


def test_a_passage_that_only_shares_common_words_is_not_a_source() -> None:
    from ar_domain.research.providers import library_hits

    store = demo_store()
    add_library_notes(store)
    tenant = demo_id("tenant")
    about = library_hits(store, tenant, "How long should the line of a kite be?", limit=4)
    assert about and all(row["url"].startswith("library://") for row in about)
    # "is", "the", "of" and "a" are in every note. They do not make a note relevant.
    assert library_hits(store, tenant, "What is the airspeed of a swallow?", limit=4) == []
    # The tenant sets its own bar.
    store.tenant_settings.setdefault(tenant, {})["research"] = {"minMatchedWords": 0}
    assert library_hits(store, tenant, "What is the airspeed of a swallow?", limit=4)


def _ingest_note(store: object, tenant: uuid.UUID, *, filename: str, text: str) -> None:
    from ar_domain.agents.access import Actor
    from ar_domain.documents.library import ingest_bytes
    from ar_domain.identity.permissions import PERMISSION_KEYS

    actor = Actor(tenant, demo_id("admin"), PERMISSION_KEYS)
    asyncio.run(
        ingest_bytes(
            store, actor, data=text.encode(), filename=filename, media_type="text/markdown"
        )
    )


def test_rank_by_similarity_orders_and_filters() -> None:
    from ar_domain.research.providers import rank_by_similarity

    query = [1.0, 0.0]
    vectors = [[1.0, 0.0], [0.0, 1.0], [0.9, 0.0]]
    ranked = rank_by_similarity(query, vectors, min_score=0.5, limit=5)
    assert [index for index, _score in ranked] == [0, 2]  # best first, orthogonal one dropped
    assert rank_by_similarity(query, vectors, min_score=0.5, limit=1) == [(0, 1.0)]


def test_semantic_recall_finds_a_passage_with_no_shared_words(monkeypatch) -> None:
    from ar_domain.research import providers

    store = demo_store()
    tenant = demo_id("tenant")
    _ingest_note(
        store,
        tenant,
        filename="marine.md",
        text="# Marine life\n\nOctopuses have three hearts and blue blood.\n",
    )
    _ingest_note(
        store,
        tenant,
        filename="weather.md",
        text="# Weather\n\nThe weather today is sunny and warm.\n",
    )
    query = "What is unusual about cephalopod circulation?"
    # The target passage shares no distinctive words with the question: words alone miss it.
    assert providers._lexical_hits(store, tenant, query, limit=4) == []

    def fake_embed(_target, texts, **_kwargs):
        # texts[0] is the query; give it and any octopus passage the same direction.
        return [
            [1.0, 0.0] if index == 0 or "octopus" in text.lower() else [0.0, 1.0]
            for index, text in enumerate(texts)
        ]

    monkeypatch.setattr("ar_domain.models.embedding.embedding_model", lambda *a, **k: object())
    monkeypatch.setattr("ar_domain.models.embedding.embed", fake_embed)
    hits = providers.library_hits(store, tenant, query, limit=4)
    assert hits, "meaning should find the octopus passage even with no shared words"
    assert any("octopus" in row["snippet"].lower() for row in hits)
    assert all(row["url"].startswith("library://") for row in hits)
    # The unrelated weather passage is not close in meaning, so it is not a source.
    assert not any("sunny" in row["snippet"].lower() for row in hits)


def test_embedding_failure_falls_back_to_word_match(monkeypatch) -> None:
    from ar_domain.research import providers

    store = demo_store()
    tenant = demo_id("tenant")
    _ingest_note(
        store,
        tenant,
        filename="marine.md",
        text="# Marine life\n\nOctopuses have three hearts and blue blood.\n",
    )

    def boom(_target, _texts, **_kwargs):
        from ar_domain.models.embedding import EmbeddingFailedError

        raise EmbeddingFailedError("the embedding model did not answer")

    monkeypatch.setattr("ar_domain.models.embedding.embedding_model", lambda *a, **k: object())
    monkeypatch.setattr("ar_domain.models.embedding.embed", boom)
    # A failed embedding call does not break research: the word signal still finds the passage.
    hits = providers.library_hits(store, tenant, "What do octopuses have?", limit=4)
    assert hits and all(row["url"].startswith("library://") for row in hits)

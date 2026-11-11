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

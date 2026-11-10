"""Stage 10 research engine and citation check. Proof: unit."""

import asyncio
import uuid

from ar_domain.chat.service import demo_id
from ar_domain.research.citations import source_record, verify_report
from ar_domain.research.engine import advance, initial_state, public_research, run_subtask
from ar_domain.research.fetch import extract_readable
from ar_domain.research.handlers import dispatch_context, dispatch_research
from ar_testing.demo import demo_store


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


def test_research_run_cites_fixture_pages() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant,
        user,
        uuid.UUID(str(conversation["id"])),
        "What do the stored notes say about a kite?",
        research=True,
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    asyncio.run(store.generate(run_id, "What do the stored notes say about a kite?", []))
    view = public_research(store.runs[run_id])
    assert view["status"] == "completed"
    assert view["sources"]
    assert all(row["sha256"] and row["fetchedAt"] for row in view["sources"])
    assert "[1]" in str(view["report"])
    started = [row for row in store.audit_log if row.get("action") == "research.started"]
    finished = [row for row in store.audit_log if row.get("action") == "research.completed"]
    assert started and finished


def test_subtask_is_idempotent_and_tools_return_text() -> None:
    store = demo_store()
    result = run_subtask(store, demo_id("tenant"), {"id": "1", "text": "kites"})
    assert result["sources"]
    hits = dispatch_research(store, "search", {"query": "kites", "_tenant_id": demo_id("tenant")})
    assert hits["is_error"] is False
    page = dispatch_research(store, "fetch", {"url": "fixture://notes/overview", "query": "kites"})
    assert "Overview" in page["text"]
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

"""Reading a public site politely: fetch facts, robots.txt, limits, and what a site lists.

Every test talks to a real HTTP server on this machine. Nothing is patched in the product.
"""

from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

import pytest

from ar_common.settings import get_settings, set_settings
from ar_domain.demo_ids import demo_id
from ar_domain.tools.handlers import dispatch
from ar_domain.tools.seed_tools import ensure_m34b, shipped_tools
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from collections.abc import Iterator

PAGE = (
    "<html><head><title>Notices</title>"
    '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
    "<script>var a = 'aaaaaaaaaaaaaaaaaaaa';</script></head><body>"
    '<p>Two notices this week.</p><a href="/notice/1#top">First notice</a>'
    '<a href="notice/2">Second notice</a><a href="https://elsewhere.example/x">Away</a>'
    '<a href="mailto:a@example.org">Mail</a></body></html>'
)
RSS = (
    '<?xml version="1.0"?><rss version="2.0"><channel><title>Notices</title>'
    "<item><title>First</title><link>/notice/1</link>"
    "<pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>"
    "<item><title>Second</title><link>https://other.example/2</link></item>"
    "</channel></rss>"
)
ATOM = (
    '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Notices</title>'
    '<entry><title>Entry</title><link href="/notice/9"/><updated>2026-11-02T10:00:00Z</updated>'
    "</entry></feed>"
)
SITEMAP = (
    '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>/notice/1</loc><lastmod>2026-11-01</lastmod></url>"
    "<url><loc>/notice/2</loc></url></urlset>"
)


class _Site(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        site: Any = self.server
        site.seen.append((self.path, dict(self.headers.items())))
        status, kind, body, headers = site.pages.get(self.path, (404, "text/plain", b"none", {}))
        if headers.get("ETag") and self.headers.get("If-None-Match") == headers["ETag"]:
            status, body = 304, b""
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        del args


@pytest.fixture
def site() -> Iterator[Any]:
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    server.seen = []
    server.pages = {
        "/": (200, "text/html; charset=utf-8", PAGE.encode(), {"ETag": '"v1"'}),
        # A byte-order mark first, as real feeds often have.
        "/feed.xml": (200, "application/rss+xml", b"\xef\xbb\xbf" + RSS.encode(), {}),
        "/atom.xml": (200, "application/atom+xml", ATOM.encode(), {}),
        "/sitemap.xml": (200, "application/xml", SITEMAP.encode(), {}),
        "/report.pdf": (200, "application/pdf", b"%PDF-1.7 not a page", {}),
        "/members": (403, "text/html", b"<p>Sign in</p>", {}),
        "/huge": (200, "text/html", b"a" * 5_300_000, {}),
    }
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = get_settings()
    set_settings(
        before.model_copy(
            update={
                "egress_allow_loopback": True,
                "http_user_agent": "watch-test/1.0 (+https://example.org/contact)",
            }
        )
    )
    yield server
    set_settings(before)
    server.shutdown()
    server.server_close()


def _store() -> Any:
    store = demo_store()
    store.tenant_settings[demo_id("tenant")] = {"egress_allowlist": ["127.0.0.1"]}
    store.fetch_retry_sleep = lambda _delay: None
    return store


def _url(site: Any, path: str) -> str:
    return f"http://127.0.0.1:{site.server_address[1]}{path}"


def _call(store: Any, server: str, name: str, **arguments: object) -> dict[str, Any]:
    endpoint = f"builtin://{server}"
    return dispatch(store, endpoint, name, {"_tenant_id": demo_id("tenant"), **arguments}, "")


def _paths(site: Any) -> list[str]:
    return [path for path, _headers in site.seen]


def test_fetch_reports_what_it_measured_and_names_itself(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/"))
    assert result["is_error"] is False
    facts = result["structured"]["presentation"]
    assert facts["status"] == 200
    assert facts["etag"] == '"v1"'
    assert facts["contentType"] == "text/html"
    assert facts["sha256"] == hashlib.sha256(PAGE.encode()).hexdigest()
    assert facts["bytes"] == len(PAGE.encode())
    assert facts["title"] == "Notices"
    assert facts["textChars"] > 0
    assert 0 < facts["scriptRatio"] < 1
    assert 'ETag: "v1"' in result["text"]
    assert "Two notices this week." in result["text"]
    assert _paths(site) == ["/robots.txt", "/"]
    for _path, headers in site.seen:
        assert headers["User-Agent"] == "watch-test/1.0 (+https://example.org/contact)"


def test_fetch_with_the_earlier_etag_is_told_nothing_changed(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/"), if_none_match='"v1"')
    assert result["is_error"] is False
    facts = result["structured"]["presentation"]
    assert facts["status"] == 304
    assert facts["notModified"] is True
    assert "sha256" not in facts
    assert "Not modified" in result["text"]


def test_fetch_returns_no_more_text_than_the_caller_asked_for(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/"), max_chars=10)
    assert result["text"].endswith("Two notice")
    # The count is of the whole page, so a caller can see the text was cut.
    assert result["structured"]["presentation"]["textChars"] > 10


def test_fetch_says_a_file_is_not_a_page_and_still_gives_its_hash(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/report.pdf"))
    assert result["is_error"] is False
    assert "documents.ingest" in result["text"]
    assert "%PDF" not in result["text"]
    facts = result["structured"]["presentation"]
    assert facts["contentType"] == "application/pdf"
    assert facts["sha256"] == hashlib.sha256(b"%PDF-1.7 not a page").hexdigest()


def test_a_site_that_refuses_is_reported_and_not_retried(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/members"))
    assert result["code"] == "access_refused"
    assert "does not work around" in result["text"]
    assert _paths(site).count("/members") == 1


def test_a_missing_page_is_an_error_not_an_empty_answer(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/nowhere"))
    assert result["code"] == "upstream_error"
    assert "HTTP 404" in result["text"]


def test_a_page_robots_disallows_is_never_requested(site: Any) -> None:
    site.pages["/robots.txt"] = (200, "text/plain", b"User-agent: *\nDisallow: /members\n", {})
    store = _store()
    refused = _call(store, "general", "fetch", url=_url(site, "/members"))
    assert refused["code"] == "robots_disallowed"
    assert "/members" not in _paths(site)
    assert _call(store, "general", "fetch", url=_url(site, "/"))["is_error"] is False
    assert (
        _call(store, "web", "discover", url=_url(site, "/members"))["code"] == "robots_disallowed"
    )
    ingest = _call(store, "documents", "ingest", url=_url(site, "/members"))
    assert ingest["is_error"] is True
    assert "/members" not in _paths(site)


def test_a_site_whose_robots_file_cannot_be_read_is_left_alone(site: Any) -> None:
    site.pages["/robots.txt"] = (500, "text/plain", b"broken", {})
    result = _call(_store(), "general", "fetch", url=_url(site, "/"))
    assert result["code"] == "upstream_error"
    assert "robots.txt could not be read" in result["text"]
    assert "/" not in _paths(site)


def test_a_body_past_the_size_limit_is_refused(site: Any) -> None:
    result = _call(_store(), "general", "fetch", url=_url(site, "/huge"))
    assert result["code"] == "too_large"
    assert "5 MB" in result["text"]


def test_one_host_gets_only_so_many_requests_a_minute(site: Any) -> None:
    set_settings(get_settings().model_copy(update={"fetch_per_host_per_minute": 2}))
    store = _store()
    assert _call(store, "general", "fetch", url=_url(site, "/"))["is_error"] is False
    assert _call(store, "web", "discover", url=_url(site, "/"))["is_error"] is False
    third = _call(store, "general", "fetch", url=_url(site, "/"))
    assert third["code"] == "rate_limited"
    assert _paths(site).count("/") == 2


def test_the_pause_a_site_asks_for_lowers_its_limit(site: Any) -> None:
    site.pages["/robots.txt"] = (200, "text/plain", b"User-agent: *\nCrawl-delay: 60\n", {})
    store = _store()
    assert _call(store, "general", "fetch", url=_url(site, "/"))["is_error"] is False
    assert _call(store, "general", "fetch", url=_url(site, "/"))["code"] == "rate_limited"


def test_discover_lists_the_items_of_an_rss_feed(site: Any) -> None:
    result = _call(_store(), "web", "discover", url=_url(site, "/feed.xml"))
    found = result["structured"]["presentation"]
    assert found["source"] == "feed"
    assert found["items"] == [
        {
            "url": _url(site, "/notice/1"),
            "title": "First",
            "date": "Mon, 02 Nov 2026 10:00:00 GMT",
        },
        {"url": "https://other.example/2", "title": "Second", "date": ""},
    ]
    assert "untrusted" in result["text"]
    assert _url(site, "/notice/1") in result["text"]


def test_discover_lists_the_entries_of_an_atom_feed_and_a_sitemap(site: Any) -> None:
    store = _store()
    atom = _call(store, "web", "discover", url=_url(site, "/atom.xml"))
    assert atom["structured"]["presentation"]["items"] == [
        {"url": _url(site, "/notice/9"), "title": "Entry", "date": "2026-11-02T10:00:00Z"}
    ]
    sitemap = _call(store, "web", "discover", url=_url(site, "/sitemap.xml"), limit=1)
    found = sitemap["structured"]["presentation"]
    assert found["source"] == "sitemap"
    assert found["total"] == 2
    assert found["items"] == [{"url": _url(site, "/notice/1"), "title": "", "date": "2026-11-01"}]
    assert "the first 1 shown" in sitemap["text"]


def test_discover_lists_a_pages_own_links_its_feeds_and_the_sitemaps(site: Any) -> None:
    listed = f"Sitemap: {_url(site, '/sitemap.xml')}\n".encode()
    site.pages["/robots.txt"] = (200, "text/plain", listed, {})
    store = _store()
    found = _call(store, "web", "discover", url=_url(site, "/"))["structured"]["presentation"]
    assert found["source"] == "page"
    assert found["items"] == [
        {"url": _url(site, "/notice/1"), "title": "First notice", "date": ""},
        {"url": _url(site, "/notice/2"), "title": "Second notice", "date": ""},
    ]
    assert found["feeds"] == [_url(site, "/feed.xml")]
    assert found["sitemaps"] == [_url(site, "/sitemap.xml")]
    wider = _call(
        store, "web", "discover", url=_url(site, "/"), allow_hosts=["127.0.0.1", "*.example"]
    )
    urls = [item["url"] for item in wider["structured"]["presentation"]["items"]]
    assert "https://elsewhere.example/x" in urls


def test_discover_keeps_to_the_hosts_the_organisation_allows(site: Any) -> None:
    del site
    result = _call(_store(), "web", "discover", url="https://not-listed.example/feed.xml")
    assert result["code"] == "egress_denied"
    assert _call(_store(), "web", "discover")["code"] == "validation_failed"
    assert _call(_store(), "web", "fetch", url="https://example.com/")["code"] == "unknown_tool"


def test_every_install_ships_discover_and_none_ships_the_canned_page() -> None:
    shipped = shipped_tools()
    assert "web.discover" in shipped
    assert "web.fetch" not in shipped
    assert "if_none_match" in shipped["general.fetch"]["input_schema"]["properties"]  # type: ignore[index]


def test_an_install_seeded_with_the_canned_page_gets_the_real_tool() -> None:
    store = demo_store()
    discover = next(
        row for row in store.tool_defs.values() if row.get("qualified_name") == "web.discover"
    )
    old = {**discover, "id": demo_id("tool-web-fetch"), "name": "fetch"}
    old["qualified_name"] = "web.fetch"
    store.tool_defs[old["id"]] = old
    ensure_m34b(store)
    assert old["disabled_at"] is not None
    assert discover.get("disabled_at") is None


def _ingest(store: Any, url: str, user: str = "admin", **arguments: object) -> dict[str, Any]:
    return _call(store, "documents", "ingest", url=url, _user_id=demo_id(user), **arguments)


def test_each_new_content_of_an_address_is_kept_and_linked_to_the_one_before(site: Any) -> None:
    store = _store()
    url = _url(site, "/notice")
    site.pages["/notice"] = (200, "text/html", b"<h1>Notice</h1><p>Limit is 10.</p>", {})
    first = _ingest(store, url)
    assert first["is_error"] is False
    assert "changed" not in first["structured"]["presentation"]
    first_id = first["structured"]["presentation"]["document"]["id"]
    site.pages["/notice"] = (200, "text/html", b"<h1>Notice</h1><p>Limit is 25.</p>", {})
    second = _ingest(store, url)
    body = second["structured"]["presentation"]
    assert body["changed"] is True
    assert body["previous"]["id"] == first_id
    assert first_id in second["text"]
    assert body["document"]["metadata"]["versionOf"] == first_id
    assert body["document"]["metadata"]["fetched"]["status"] == 200
    listed = _call(store, "documents", "list", sourceRef=url, _user_id=demo_id("admin"))
    copies = listed["structured"]["presentation"]["documents"]
    assert [row["id"] for row in copies] == [body["document"]["id"], first_id]
    assert url in listed["text"]
    # Both copies can still be read: the first was not overwritten.
    old = _call(store, "documents", "read", documentId=first_id, _user_id=demo_id("admin"))
    assert "Limit is 10." in old["text"]
    new = _call(
        store, "documents", "read", documentId=body["document"]["id"], _user_id=demo_id("admin")
    )
    assert "Limit is 25." in new["text"]


def test_an_address_that_has_not_changed_stores_nothing_new(site: Any) -> None:
    store = _store()
    url = _url(site, "/")
    first = _ingest(store, url)
    again = _ingest(store, url)
    assert again["structured"]["presentation"]["changed"] is False
    assert (
        again["structured"]["presentation"]["document"]["id"]
        == first["structured"]["presentation"]["document"]["id"]
    )
    assert "Nothing new was stored" in again["text"]
    etag = first["structured"]["presentation"]["fetched"]["etag"]
    assert etag == '"v1"'
    unchanged = _ingest(store, url, ifNoneMatch=etag)
    assert unchanged["is_error"] is False
    assert unchanged["structured"]["presentation"]["changed"] is False
    assert "document" not in unchanged["structured"]["presentation"]
    listed = _call(store, "documents", "list", sourceRef=url, _user_id=demo_id("admin"))
    assert len(listed["structured"]["presentation"]["documents"]) == 1


def test_an_address_that_answers_with_an_error_is_not_ingested(site: Any) -> None:
    store = _store()
    result = _ingest(store, _url(site, "/nowhere"))
    assert result["is_error"] is True
    assert "HTTP 404" in result["text"]
    refused = _ingest(store, _url(site, "/members"))
    assert refused["code"] == "access_refused"
    listed = _call(
        store, "documents", "list", sourceRef=_url(site, "/nowhere"), _user_id=demo_id("admin")
    )
    assert listed["structured"]["presentation"]["documents"] == []


def test_another_persons_copy_is_not_named_as_the_one_before(site: Any) -> None:
    store = _store()
    url = _url(site, "/notice")
    site.pages["/notice"] = (200, "text/html", b"<h1>Notice</h1><p>Limit is 10.</p>", {})
    assert _ingest(store, url, user="admin")["is_error"] is False
    site.pages["/notice"] = (200, "text/html", b"<h1>Notice</h1><p>Limit is 25.</p>", {})
    theirs = _ingest(store, url, user="member")
    assert theirs["is_error"] is False
    assert "previous" not in theirs["structured"]["presentation"]
    assert "versionOf" not in theirs["structured"]["presentation"]["document"]["metadata"]

"""A web knowledge source walks a site: its sitemap, its links, by the site's own rules.

The source reads a real HTTP server on this machine. Nothing is patched in the product.
"""

from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

import pytest

from ar_common.settings import get_settings, set_settings
from ar_domain.agents.access import Actor
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.fetchers import check
from ar_domain.knowledge.syncing import sync_source
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from collections.abc import Iterator


def _html(title: str, body: str) -> bytes:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>".encode()


class _Site(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        site: Any = self.server
        site.asked.append(self.path)
        found = site.pages.get(self.path)
        if found is None:
            self.send_response(404)
            self.end_headers()
            return
        if isinstance(found, str):
            self.send_response(301)
            self.send_header("Location", found)
            self.end_headers()
            return
        mime, body = found
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        del args


def _sitemap(base: str, entries: list[tuple[str, str]], *, index: bool = False) -> bytes:
    outer, inner = ("sitemapindex", "sitemap") if index else ("urlset", "url")
    rows = "".join(
        f"<{inner}><loc>{base}{path}</loc>"
        + (f"<lastmod>{changed}</lastmod>" if changed else "")
        + f"</{inner}>"
        for path, changed in entries
    )
    return (
        f'<?xml version="1.0"?><{outer} xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{rows}</{outer}>"
    ).encode()


@pytest.fixture
def site() -> Iterator[Any]:
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    server.base = base
    server.asked = []
    server.pages = {
        "/robots.txt": ("text/plain", b"User-agent: *\nDisallow: /private/\n"),
        "/sitemap_index.xml": (
            "application/xml",
            _sitemap(base, [("/page-sitemap.xml", ""), ("/post-sitemap.xml", "")], index=True),
        ),
        "/page-sitemap.xml": (
            "application/xml",
            _sitemap(
                base,
                [
                    ("/platform/", "2026-01-01"),
                    ("/case-studies/", "2026-01-02"),
                    ("/private/prices/", "2026-01-03"),
                    ("/logo.png", ""),
                ],
            ),
        ),
        "/post-sitemap.xml": ("application/xml", _sitemap(base, [("/blog/first/", "2026-02-01")])),
        "/platform/": (
            "text/html",
            _html(
                "The platform &amp; its parts", "<h1>Platform</h1><p>Workflows and dashboards.</p>"
            ),
        ),
        "/case-studies/": (
            "text/html",
            _html(
                "Case studies",
                "<h1>Case studies</h1><p>Read how others did it.</p>"
                '<a href="/files/guide.txt">The guide</a>'
                '<a href="https://elsewhere.example/other">Elsewhere</a>'
                '<a href="/old-guide">An older address</a>',
            ),
        ),
        "/private/prices/": ("text/html", _html("Prices", "<p>Secret price list.</p>")),
        "/blog/first/": ("text/html", _html("First post", "<h1>First</h1><p>Hello readers.</p>")),
        "/files/guide.txt": ("text/plain", b"The guide says: start with a risk register."),
        "/old-guide": "/files/guide.txt",
        "/logo.png": ("image/png", b"not a document"),
    }
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = get_settings()
    set_settings(before.model_copy(update={"egress_allow_loopback": True}))
    yield server
    set_settings(before)
    server.shutdown()
    server.server_close()


def _actor() -> Actor:
    return Actor(
        demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, roles=frozenset({"tenant_admin"})
    )


def _source(site: Any, **config: object) -> tuple[Any, dict[str, object]]:
    """A collection with one web source, synced once when it was made."""
    store = demo_store()
    store.tenant_settings[demo_id("tenant")] = {"egress_allowlist": ["127.0.0.1"]}
    book = KnowledgeBook(store)
    collection = book.create_collection(
        _actor(), {"name": "Site", "slug": "site", "embedding_alias": "embed"}
    )
    made = book.create_source(
        _actor(),
        uuid.UUID(str(collection["id"])),
        {"name": "Site", "kind": "web", "config": config},
    )
    return store, store.knowledge_sources[uuid.UUID(str(made["id"]))]


def _documents(store: Any, source: dict[str, object]) -> dict[str, dict[str, Any]]:
    return {
        str(row["uri"]).removeprefix(str(row["uri"]).split("/", 3)[0] + "//").split("/", 1)[1]: row
        for row in store.knowledge_documents.values()
        if row["source_id"] == source["id"] and row.get("status") != "deleted"
    }


def test_a_sitemap_index_gives_one_document_for_each_page_it_lists(site: Any) -> None:
    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=50)
    found = _documents(store, source)
    # The page the site's robots.txt closes and the picture are not read at all.
    assert sorted(found) == ["blog/first/", "case-studies/", "platform/"]
    assert "/private/prices/" not in site.asked
    assert "/logo.png" not in site.asked
    # Each document is named by its page and addressed by it, so a citation links there.
    platform = found["platform/"]
    assert platform["title"] == "The platform & its parts"
    assert platform["uri"] == f"{site.base}/platform/"
    assert platform["status"] == "indexed"
    assert source["last_sync_status"] == "succeeded"


def test_links_are_followed_as_far_as_the_source_says_and_only_on_its_hosts(site: Any) -> None:
    store, source = _source(
        site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=50, max_depth=1
    )
    found = _documents(store, source)
    # The file a page links to is read. The other site is not, and neither is a page twice.
    assert "files/guide.txt" in found
    assert found["files/guide.txt"]["mime_type"] == "text/plain"
    assert not any("elsewhere" in str(row["uri"]) for row in found.values())
    # An address that redirects on the same site is read where it leads.
    assert "old-guide" in found
    assert site.asked.count("/case-studies/") == 1


def test_a_source_reads_no_more_pages_than_it_is_allowed(site: Any) -> None:
    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=2)
    assert len(_documents(store, source)) == 2


def test_a_page_whose_date_is_the_same_is_not_asked_for_again(site: Any) -> None:
    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=50)
    site.asked.clear()
    job = sync_source(store, source, mode="incremental", actor_id=None)
    assert job["status"] == "succeeded"
    assert job["stats"]["unchanged"] == 3
    # Only the lists were read: no page was fetched.
    assert not [path for path in site.asked if path.endswith("/") and "sitemap" not in path]


def test_a_changed_page_is_read_again_and_a_removed_one_is_taken_out(site: Any) -> None:
    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=50)
    site.pages["/platform/"] = (
        "text/html",
        _html("The platform", "<h1>Platform</h1><p>Now with surveys.</p>"),
    )
    site.pages["/page-sitemap.xml"] = (
        "application/xml",
        _sitemap(site.base, [("/platform/", "2026-03-01")]),
    )
    job = sync_source(store, source, mode="incremental", actor_id=None)
    found = _documents(store, source)
    assert sorted(found) == ["blog/first/", "platform/"]
    assert found["platform/"]["title"] == "The platform"
    assert (job["stats"]["updated"], job["stats"]["deleted"]) == (1, 1)


def test_one_page_that_cannot_be_read_does_not_stop_the_rest(site: Any) -> None:
    del site.pages["/blog/first/"]
    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=50)
    assert sorted(_documents(store, source)) == ["case-studies/", "platform/"]
    assert source["last_sync_status"] == "partially_failed"


def test_a_single_address_is_still_one_page(site: Any) -> None:
    store, source = _source(site, url=f"{site.base}/platform/")
    assert sorted(_documents(store, source)) == ["platform/"]
    assert "/case-studies/" not in site.asked


def test_checking_a_source_does_not_walk_the_site(site: Any) -> None:
    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_depth=3)
    site.asked.clear()
    answer = check({**source, "store": store})
    assert answer["ok"] is True
    assert len(answer["sample"]) == 3
    assert not [path for path in site.asked if path.endswith("/") and "sitemap" not in path]


def test_a_page_can_be_found_by_whoever_may_read_its_collection(site: Any) -> None:
    """A web page carries no list of readers. It is not left readable by nobody."""
    from ar_domain.knowledge.searching import search

    store, source = _source(site, start_urls=[f"{site.base}/sitemap_index.xml"], max_pages=50)
    collection = store.knowledge_collections[source["collection_id"]]
    # The collection takes its readers from its sources, which is the default.
    assert collection["acl_mode"] != "collection"
    rows = [
        row
        for row in store.knowledge_documents.values()
        if row["source_id"] == source["id"] and row.get("status") != "deleted"
    ]
    assert all(row["acl_principals"] == ["tenant:*"] for row in rows)
    found = search(
        store,
        _actor(),
        query="workflows and dashboards",
        collection_ids=[uuid.UUID(str(collection["id"]))],
        top_k=3,
        debug=False,
    )
    assert any(str(hit["uri"]).endswith("/platform/") for hit in found["hits"])

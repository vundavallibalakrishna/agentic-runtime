"""A knowledge source keeps every version of what it fetched, in the file store.

The web source reads a real HTTP server on this machine. Nothing is patched in the product.
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
from ar_domain.durability.store import read_blob
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.members import add_member, refresh_document
from ar_domain.knowledge.pipeline import stored_bytes
from ar_domain.knowledge.syncing import reindex, sync_source
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Site(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        site: Any = self.server
        site.seen.append((self.path, self.headers.get("If-None-Match")))
        if self.path == "/robots.txt":
            self.send_response(404)
            self.end_headers()
            return
        body, etag = site.page
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        del args


@pytest.fixture
def site() -> Iterator[Any]:
    server: Any = ThreadingHTTPServer(("127.0.0.1", 0), _Site)
    server.seen = []
    server.page = (b"<h1>Notice</h1><p>The limit is 10.</p>", '"a"')
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


def _watched(site: Any) -> tuple[Any, KnowledgeBook, dict[str, object], uuid.UUID]:
    """A collection with one web source that has been synced once."""
    store = demo_store()
    store.tenant_settings[demo_id("tenant")] = {"egress_allowlist": ["127.0.0.1"]}
    book = KnowledgeBook(store)
    actor = _actor()
    collection = book.create_collection(
        actor, {"name": "Watched", "slug": "watched", "embedding_alias": "embed"}
    )
    url = f"http://127.0.0.1:{site.server_address[1]}/notice"
    made = book.create_source(
        actor,
        uuid.UUID(str(collection["id"])),
        {"name": "Notice", "kind": "web", "config": {"url": url}},
    )
    source = store.knowledge_sources[uuid.UUID(str(made["id"]))]
    [document] = [
        row for row in store.knowledge_documents.values() if row["source_id"] == source["id"]
    ]
    return store, book, source, uuid.UUID(str(document["id"]))


def _revisions(book: KnowledgeBook, document_id: uuid.UUID) -> list[dict[str, Any]]:
    return book.get_document(_actor(), document_id)["revisions"]  # type: ignore[return-value]


def test_the_first_sync_stores_the_page_as_a_file(site: Any) -> None:
    store, book, source, document_id = _watched(site)
    document = store.knowledge_documents[document_id]
    assert document["status"] == "indexed"
    file_row = store.files[document["raw_file_id"]]
    assert file_row["kind"] == "knowledge_raw"
    assert "/knowledge_raw/" in file_row["object_key"]
    assert stored_bytes(store, document_id) == site.page[0]
    [revision] = _revisions(book, document_id)
    assert revision["file_id"] == str(document["raw_file_id"])
    assert revision["version_hash"] == file_row["sha256"]
    assert revision["metadata"]["etag"] == '"a"'
    assert source["cursor"]["etag"] == '"a"'


def test_an_unchanged_page_is_asked_for_with_its_etag_and_stores_nothing(site: Any) -> None:
    store, book, source, document_id = _watched(site)
    site.seen.clear()
    job = sync_source(store, source, mode="incremental", actor_id=None)
    assert job["status"] == "succeeded"
    assert ("/notice", '"a"') in site.seen
    assert source["cursor"]["etag"] == '"a"'
    assert len(_revisions(book, document_id)) == 1
    assert store.knowledge_documents[document_id]["status"] == "indexed"


def test_a_changed_page_adds_a_version_and_keeps_the_earlier_one(site: Any) -> None:
    store, book, source, document_id = _watched(site)
    first_file = store.knowledge_documents[document_id]["raw_file_id"]
    old = site.page[0]
    site.page = (b"<h1>Notice</h1><p>The limit is 25.</p>", '"b"')
    sync_source(store, source, mode="incremental", actor_id=None)
    document = store.knowledge_documents[document_id]
    assert document["raw_file_id"] != first_file
    assert stored_bytes(store, document_id) == site.page[0]
    newest, earlier = _revisions(book, document_id)
    assert newest["file_id"] == str(document["raw_file_id"])
    assert newest["metadata"]["etag"] == '"b"'
    assert earlier["file_id"] == str(first_file)
    # The earlier version was not overwritten: its bytes are still read back.
    assert read_blob(store, first_file) == old
    assert source["cursor"]["etag"] == '"b"'


def test_a_full_sync_of_an_unchanged_page_keeps_the_document_and_adds_no_version(
    site: Any,
) -> None:
    store, book, source, document_id = _watched(site)
    site.seen.clear()
    sync_source(store, source, mode="full", actor_id=None)
    # A full sync reads the page whatever the site would say about it.
    assert ("/notice", None) in site.seen
    assert store.knowledge_documents[document_id]["status"] == "indexed"
    assert len(_revisions(book, document_id)) == 1


def test_a_collection_is_reindexed_from_the_stored_bytes(site: Any) -> None:
    store, book, _source, document_id = _watched(site)
    collection = store.knowledge_collections[
        store.knowledge_documents[document_id]["collection_id"]
    ]
    # Nothing but the file store holds the bytes: a process that did not fetch them reads it.
    store.blobs.clear()
    reindex(store, collection, actor_id=None)
    assert store.knowledge_documents[document_id]["status"] == "indexed"
    assert book.chunks(_actor(), document_id)


async def test_typed_text_is_kept_so_it_can_be_indexed_again() -> None:
    store = demo_store()
    actor = _actor()
    made = KnowledgeBook(store).create_collection(
        actor, {"name": "Notes", "slug": "notes", "embedding_alias": "embed"}
    )
    collection_id = uuid.UUID(str(made["id"]))
    added = await add_member(
        store, actor, collection_id, {"kind": "text", "title": "Note", "text": "Badge is blue."}
    )
    document_id = uuid.UUID(str(added["document"]["id"]))
    assert stored_bytes(store, document_id) == b"Badge is blue."
    refreshed = await refresh_document(store, actor, document_id)
    assert refreshed["result"] == "indexed"
    assert len(KnowledgeBook(store).get_document(actor, document_id)["revisions"]) == 1  # type: ignore[arg-type]

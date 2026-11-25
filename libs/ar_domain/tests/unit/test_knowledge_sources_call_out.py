"""A knowledge source reads from the system it names. OQ-197.

Found on 25 November 2026: the ``s3``, ``database`` and ``mcp_resource`` kinds made no
call at all. They indexed rows written into the source's own configuration, and every
kind accepted an ``items`` list in place of the source. Each kind now calls out:
``ListObjectsV2`` and ``GetObject``, one guarded query on a data connection, and
``resources/list`` and ``resources/read`` on a registered MCP server.

The services here are the test library's: an S3 client, a database and an MCP endpoint a
test owns. The product code under test is the same code an install runs.
"""

from __future__ import annotations

import base64
import io
import uuid
from typing import Any

import httpx
import pytest

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.fetchers import check, list_changes
from ar_domain.knowledge.syncing import sync_source
from ar_domain.tools.seed_tools import approved_server
from ar_domain.tools.service_connections import ConnectionBook
from ar_testing.demo import demo_store
from ar_testing.stand_in import shared

pytestmark = pytest.mark.unit


def _admin() -> Actor:
    return Actor(
        demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, roles=frozenset({"tenant_admin"})
    )


def _collection(store: ChatService, slug: str, **more: object) -> uuid.UUID:
    created = KnowledgeBook(store).create_collection(_admin(), {"slug": slug, "name": slug, **more})
    return uuid.UUID(str(created["id"]))


def _titles(store: ChatService, collection_id: uuid.UUID) -> set[str]:
    return {
        str(row["title"])
        for row in store.knowledge_documents.values()
        if row.get("collection_id") == collection_id and row.get("status") != "deleted"
    }


class _Bucket:
    """An S3 client over a dict, paged two keys at a time as the service pages."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.listed: list[dict[str, object]] = []
        self.read: list[str] = []

    def list_objects_v2(self, **request: Any) -> dict[str, object]:
        self.listed.append(dict(request))
        keys = sorted(key for key in self.objects if key.startswith(str(request["Prefix"])))
        start = int(str(request.get("ContinuationToken") or "0"))
        page = keys[start : start + 2]
        more = start + 2 < len(keys)
        return {
            "Contents": [
                {"Key": key, "Size": len(self.objects[key]), "ETag": f'"{hash(self.objects[key])}"'}
                for key in page
            ],
            "IsTruncated": more,
            "NextContinuationToken": str(start + 2) if more else "",
        }

    def get_object(self, **request: Any) -> dict[str, object]:
        self.read.append(str(request["Key"]))
        return {"Body": io.BytesIO(self.objects[str(request["Key"])])}


def _s3_source(store: ChatService, collection_id: uuid.UUID, **config: object) -> dict[str, object]:
    ConnectionBook(store).create(
        _admin(),
        {"name": "bucket-keys", "kind": "basic", "username": "AKIDEXAMPLE", "secret": "s3-secret"},
    )
    return KnowledgeBook(store).create_source(
        _admin(),
        collection_id,
        {
            "name": "Handbooks",
            "kind": "s3",
            "config": {"bucket": "handbooks", "connection": "bucket-keys", **config},
        },
    )


def test_an_s3_source_lists_every_page_and_reads_each_object() -> None:
    store = demo_store()
    bucket = _Bucket(
        {
            "docs/visitors.md": b"# Visitors\n\nThe visitor desk opens at 08:30.",
            "docs/payroll.md": b"# Payroll\n\nPayroll is released on the 28th.",
            "docs/roster.md": b"# Roster\n\nDev Member is on call.",
            "other/skip.md": b"not under the prefix",
        }
    )
    store.connector_s3 = lambda: bucket  # type: ignore[attr-defined]
    collection_id = _collection(store, "s3-library", acl_mode="collection")
    source = _s3_source(store, collection_id, prefix="docs/")
    assert source["last_sync_status"] == "succeeded"
    assert _titles(store, collection_id) == {"visitors.md", "payroll.md", "roster.md"}
    # Three keys, two to a page: the second page was asked for with the token of the first.
    assert [row.get("ContinuationToken") for row in bucket.listed] == [None, "2"]
    assert sorted(bucket.read) == ["docs/payroll.md", "docs/roster.md", "docs/visitors.md"]
    found = KnowledgeBook(store).search(
        _admin(), {"query": "visitor desk", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "visitors.md" for hit in found["hits"])
    # The secret key opened the connection and is on no stored row.
    assert "s3-secret" not in str(store.knowledge_sources) + str(store.knowledge_documents)


def test_an_object_removed_from_the_bucket_is_removed_from_the_collection() -> None:
    store = demo_store()
    bucket = _Bucket({"a.md": b"# A\n\nFirst.", "b.md": b"# B\n\nSecond."})
    store.connector_s3 = lambda: bucket  # type: ignore[attr-defined]
    collection_id = _collection(store, "s3-shrinks", acl_mode="collection")
    source = _s3_source(store, collection_id)
    assert _titles(store, collection_id) == {"a.md", "b.md"}
    del bucket.objects["b.md"]
    bucket.read.clear()
    row = store.knowledge_sources[uuid.UUID(str(source["id"]))]
    job = sync_source(store, row, mode="incremental", actor_id=_admin().user_id)
    assert job["status"] == "succeeded"
    assert _titles(store, collection_id) == {"a.md"}


def test_an_s3_source_says_what_it_is_missing() -> None:
    store = demo_store()
    source: dict[str, object] = {
        "kind": "s3",
        "store": store,
        "tenant_id": demo_id("tenant"),
        "created_by": demo_id("admin"),
        "config": {"bucket": "handbooks"},
    }
    assert "stored connection" in str(list_changes(source, mode="full")["error"])
    source["config"] = {"bucket": "handbooks", "connection": "nobody-made-this"}
    answer = check(source)
    assert answer["ok"] is False
    assert "nobody-made-this" in str(answer["error"])


def _warehouse_source(
    store: ChatService, collection_id: uuid.UUID, **config: object
) -> dict[str, object]:
    return KnowledgeBook(store).create_source(
        _admin(),
        collection_id,
        {
            "name": "Orders",
            "kind": "database",
            "data_connection_id": str(demo_id("connection-warehouse")),
            "config": {"query": "SELECT id, sku, quantity FROM public.orders", **config},
        },
    )


def test_a_database_source_runs_its_query_and_makes_a_document_of_each_row() -> None:
    store = demo_store()
    collection_id = _collection(store, "orders", acl_mode="collection")
    source = _warehouse_source(store, collection_id, titleColumn="sku")
    assert source["last_sync_status"] == "succeeded"
    assert _titles(store, collection_id) == {"paper", "ink", "stapler"}
    found = KnowledgeBook(store).search(
        _admin(), {"query": "stapler", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "stapler" for hit in found["hits"])


def test_a_database_source_refuses_a_write_and_a_missing_id_column() -> None:
    store = demo_store()
    base: dict[str, object] = {
        "kind": "database",
        "store": store,
        "tenant_id": demo_id("tenant"),
        "data_connection_id": str(demo_id("connection-warehouse")),
    }
    written = list_changes({**base, "config": {"query": "DELETE FROM public.orders"}}, mode="full")
    assert written["items"] == []
    assert written["error"], "the SQL guard refuses a statement that is not a read"
    no_id = list_changes(
        {**base, "config": {"query": "SELECT sku FROM public.orders", "idColumn": "order_id"}},
        mode="full",
    )
    assert "order_id" in str(no_id["error"])
    unbound = list_changes({**base, "data_connection_id": None, "config": {}}, mode="full")
    assert "data connection" in str(unbound["error"])


def _mcp(resources: dict[str, dict[str, object]]) -> tuple[httpx.MockTransport, list[str]]:
    """An MCP endpoint that lists ``resources`` one to a page and reads them."""
    seen: list[str] = []
    order = sorted(resources)

    def send(request: httpx.Request) -> httpx.Response:
        import orjson

        body = orjson.loads(request.content)
        method = str(body.get("method"))
        seen.append(method)
        if method == "resources/list":
            at = int(str((body.get("params") or {}).get("cursor") or "0"))
            result: dict[str, object] = {
                "resources": [{"uri": order[at], "name": order[at].rsplit("/", 1)[-1]}]
            }
            if at + 1 < len(order):
                result["nextCursor"] = str(at + 1)
        elif method == "resources/read":
            uri = str(body["params"]["uri"])
            result = {"contents": [{"uri": uri, **resources[uri]}]}
        else:
            result = {"protocolVersion": "2025-06-18", "capabilities": {}}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body.get("id"), "result": result})

    return httpx.MockTransport(send), seen


def _register_notes_server(store: ChatService, *, auth_mode: str = "none") -> None:
    approved_server(
        store,
        tenant_id=demo_id("tenant"),
        owner=demo_id("admin"),
        slug="notes",
        name="Notes",
        description="A remote server that holds notes as resources.",
        kind="remote_mcp",
        endpoint="https://example.com/mcp",
        auth_mode=auth_mode,
        provider_id=None,
        tools=[],
        config={},
    )


def test_an_mcp_resource_source_lists_and_reads_resources_from_the_server() -> None:
    store = demo_store()
    transport, seen = _mcp(
        {
            "notes://desk": {"mimeType": "text/markdown", "text": "# Desk\n\nOpens at 08:30."},
            "notes://badge": {
                "mimeType": "text/plain",
                "blob": base64.b64encode(b"Bring a badge to the visitor desk.").decode(),
            },
        }
    )
    store.mcp_transport = transport  # type: ignore[attr-defined]
    _register_notes_server(store)
    collection_id = _collection(store, "mcp-notes", acl_mode="collection")
    source = KnowledgeBook(store).create_source(
        _admin(),
        collection_id,
        {"name": "Notes", "kind": "mcp_resource", "config": {"server": "notes"}},
    )
    assert source["last_sync_status"] == "succeeded"
    assert _titles(store, collection_id) == {"desk", "badge"}
    assert seen.count("resources/list") == 2, "the second page was followed"
    assert seen.count("resources/read") == 2
    found = KnowledgeBook(store).search(
        _admin(), {"query": "badge", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "badge" for hit in found["hits"])


def test_an_mcp_resource_source_reads_over_http_from_a_running_server() -> None:
    """The same calls with no transport set: a request leaves the process and comes back."""
    store = demo_store()
    address = shared().serve_resources(
        "handbook",
        {
            "handbook://visitors": {
                "mimeType": "text/markdown",
                "text": "# Visitors\n\nThe visitor desk opens at 08:30.",
            },
            "handbook://payroll": {
                "mimeType": "text/markdown",
                "text": "# Payroll\n\nPayroll is released on the 28th.",
            },
        },
    )
    approved_server(
        store,
        tenant_id=demo_id("tenant"),
        owner=demo_id("admin"),
        slug="handbook",
        name="Handbook",
        description="A running MCP server that holds the handbook.",
        kind="remote_mcp",
        endpoint=address,
        auth_mode="none",
        provider_id=None,
        tools=[],
        config={},
    )
    collection_id = _collection(store, "mcp-http", acl_mode="collection")
    source = KnowledgeBook(store).create_source(
        _admin(),
        collection_id,
        {"name": "Handbook", "kind": "mcp_resource", "config": {"server": "handbook"}},
    )
    assert source["last_sync_status"] == "succeeded"
    assert _titles(store, collection_id) == {"visitors", "payroll"}
    # A resource the server stops listing is removed on the next sync.
    shared().serve_resources(
        "handbook", {"handbook://visitors": {"mimeType": "text/markdown", "text": "# Visitors"}}
    )
    row = store.knowledge_sources[uuid.UUID(str(source["id"]))]
    sync_source(store, row, mode="incremental", actor_id=_admin().user_id)
    assert _titles(store, collection_id) == {"visitors"}


def test_an_mcp_resource_source_says_why_it_cannot_read() -> None:
    store = demo_store()
    base: dict[str, object] = {
        "kind": "mcp_resource",
        "store": store,
        "tenant_id": demo_id("tenant"),
        "created_by": demo_id("admin"),
    }
    assert "registered tool server" in str(
        list_changes({**base, "config": {}}, mode="full")["error"]
    )
    missing = list_changes({**base, "config": {"server": "notes"}}, mode="full")
    assert "notes" in str(missing["error"])
    _register_notes_server(store, auth_mode="user_oauth")
    personal = list_changes({**base, "config": {"server": "notes"}}, mode="full")
    assert "stored connection" in str(personal["error"])


def test_a_high_sensitivity_search_asks_the_source_who_may_read_now() -> None:
    """Late verification: the reader list is read again from the source at search time."""
    store = demo_store()
    store.user_emails[demo_id("admin")] = "admin@dev.local"
    store.company_domains = {"dev.local"}
    row = {
        "id": "roster",
        "title": "Roster",
        "text": "Dev Member is on call this week.",
        "acl": [{"type": "user", "email": "admin@dev.local"}],
    }
    address = shared().serve_json("late-check", {"value": [row]})
    collection_id = _collection(store, "late", sensitivity="high", acl_mode="source")
    KnowledgeBook(store).create_source(
        _admin(),
        collection_id,
        {"name": "Drive", "kind": "google_drive", "config": {"url": address}},
    )
    ask = {"query": "on call", "collection_ids": [collection_id]}
    assert KnowledgeBook(store).search(_admin(), ask)["hits"]
    # The source takes the admin off the document. Nothing has been synced since.
    shared().serve_json(
        "late-check", {"value": [{**row, "acl": [{"type": "user", "email": "other@dev.local"}]}]}
    )
    assert KnowledgeBook(store).search(_admin(), ask)["hits"] == []
    # A source that does not answer is a refusal, not a pass.
    shared().serve_json("late-check", "not a listing")
    assert KnowledgeBook(store).search(_admin(), ask)["hits"] == []

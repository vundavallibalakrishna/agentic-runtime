"""Parsers, fetchers, connectors and the model gateway embedding path."""

import asyncio
import io
import uuid
import zipfile

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge import tables
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.citations import (
    as_uuid,
    marker,
    new_evidence,
    public_citation,
    readable,
    tool_result_citation,
)
from ar_domain.knowledge.fetchers import check_access, list_acl_changes, list_changes
from ar_domain.knowledge.parse import ParseError, parse_bytes
from ar_domain.knowledge.retrieval import merge_groups, search_targets
from ar_domain.knowledge.store import memory_index
from ar_domain.knowledge.store_types import ScoredChunk, SearchTarget
from ar_ingest.connectors import (
    ConfluenceSource,
    DatabaseSource,
    GoogleDriveSource,
    McpResourceSource,
    S3Source,
    SharePointSource,
    UploadSource,
    WebSource,
)
from ar_ingest.workflows import acl_sync as _acl_workflow
from ar_ingest.workflows import delete_document as _delete_workflow
from ar_ingest.workflows import ingest_document as _ingest_workflow
from ar_ingest.workflows import reindex_collection as _reindex_workflow
from ar_ingest.workflows import retrieval_store_audit as _audit_workflow
from ar_ingest.workflows import source_sync as _sync_workflow
from ar_model_gateway.main import create_application
from ar_runtime import citations as runtime_citations
from ar_runtime import grounding as runtime_grounding

pytestmark = pytest.mark.unit


def _zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        for name, body in entries.items():
            book.writestr(name, body)
    return buffer.getvalue()


def test_parsers_read_office_html_and_csv() -> None:
    html = parse_bytes(
        b"<html><body><p>Visitor desk</p><script>x</script></body></html>",
        mime_type="text/html",
        name="a.html",
        max_bytes=1000,
    )
    assert "Visitor desk" in html
    table = parse_bytes(
        b"month,revenue\nJan,10\n", mime_type="text/csv", name="a.csv", max_bytes=1000
    )
    assert "Jan" in table
    pptx = _zip(
        {
            "ppt/slides/slide1.xml": '<a xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>Desk</a:t></a>'
        }
    )
    assert "Desk" in parse_bytes(
        pptx,
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        name="a.pptx",
        max_bytes=10_000,
    )
    sheet = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shared = f'<x xmlns:x="{sheet[1:-1]}"><x:si><x:t>Desk</x:t></x:si></x>'
    grid = f'<x xmlns:x="{sheet[1:-1]}"><x:row><x:c t="s"><x:v>0</x:v></x:c></x:row></x>'
    xlsx = _zip({"xl/sharedStrings.xml": shared, "xl/worksheets/sheet1.xml": grid})
    assert "Desk" in parse_bytes(
        xlsx,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        name="a.xlsx",
        max_bytes=10_000,
    )
    with pytest.raises(ParseError):
        parse_bytes(b"not-a-zip", mime_type="application/pdf", name="bad.pptx", max_bytes=100)
    assert tables.KnowledgeCollection.__tablename__ == "knowledge_collections"
    assert _ingest_workflow.IngestDocumentWorkflow
    assert _sync_workflow.SourceSyncWorkflow
    assert _acl_workflow.AclSyncWorkflow
    assert _delete_workflow.DeleteDocumentWorkflow
    assert _reindex_workflow.ReindexCollectionWorkflow
    assert _audit_workflow.RetrievalStoreAuditWorkflow
    assert runtime_citations.allocate and runtime_grounding.apply_grounding


def test_fetchers_and_connectors_use_recorded_http() -> None:
    with respx.mock:
        respx.get("https://example.com/robots.txt").mock(
            return_value=httpx.Response(200, text="Allow: /")
        )
        respx.get("https://example.com/guide").mock(
            return_value=httpx.Response(200, text="<p>Desk</p>", headers={"etag": "abc"})
        )
        page = list_changes(
            {
                "kind": "web",
                "config": {"url": "https://example.com/guide", "allowlist": ["example.com"]},
            },
            mode="full",
        )
        assert page["items"][0]["title"]
        respx.get("https://graph.test/delta").mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        {"id": "1", "title": "Page", "deleted": False},
                        {"id": "2", "deleted": True},
                    ]
                },
            )
        )
        graph = list_changes(
            {"kind": "sharepoint", "config": {"url": "https://graph.test/delta", "token": "t"}},
            mode="incremental",
        )
        assert graph["deleted_external_ids"] == ["2"]
    blocked = list_changes(
        {"kind": "web", "config": {"url": "https://example.com", "allowlist": ["other.test"]}},
        mode="full",
    )
    assert blocked["items"] == []
    s3 = list_changes(
        {"kind": "s3", "config": {"objects": [{"key": "a.txt", "text": "hello"}]}},
        mode="full",
    )
    assert s3["items"][0]["external_id"] == "a.txt"
    source = {
        "kind": "web",
        "config": {"items": [{"external_id": "p", "title": "Page", "acl": [{"type": "anyone"}]}]},
    }
    connector = WebSource(source)
    assert connector.list_changes(None)["items"]
    assert connector.fetch({"text": "hi"})[0] == b"hi"
    assert connector.list_acl_changes(None) == list_acl_changes(source)
    assert connector.check_access("p", "user") is check_access(source, "p", "user")
    for cls in (
        S3Source,
        SharePointSource,
        ConfluenceSource,
        GoogleDriveSource,
        DatabaseSource,
        McpResourceSource,
        UploadSource,
    ):
        assert cls({"kind": cls.kind, "config": {"items": []}}).check()["ok"]


def test_citations_plan_limits_and_gateway() -> None:
    assert marker(1) == "[1]"
    evidence = new_evidence("Policy", "evidence://1", "kept")
    assert public_citation(evidence)["source_kind"] == "evidence_item"
    assert (
        tool_result_citation("Tool", "https://example.com", "out")["source_kind"] == "tool_result"
    )
    assert as_uuid("not-a-uuid") is None
    assert as_uuid("") is None
    store = ChatService()
    admin = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS, roles=frozenset({"tenant_admin"}))
    book = KnowledgeBook(store)
    store.tenant_settings[admin.tenant_id] = {"plan_limits": {"max_collections": 0}}
    with pytest.raises(Exception):
        book.create_collection(admin, {"slug": "full", "name": "Full"})
    store.tenant_settings[admin.tenant_id] = {"plan_limits": {"max_knowledge_documents": 0}}
    created = book.create_collection(admin, {"slug": "box", "name": "Box", "visibility": "private"})
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "tenant_id": admin.tenant_id,
        "owner_user_id": admin.user_id,
        "status": "ready",
        "name": "a.md",
        "mime_type": "text/markdown",
    }
    store.blobs[file_id] = b"hello"
    with pytest.raises(Exception):
        book.add_documents(admin, uuid.UUID(str(created["id"])), {"file_ids": [str(file_id)]})
    assert readable(store, admin, {"source_kind": "tool_result"})
    assert not readable(store, admin, {"source_kind": "knowledge", "document_id": "nope"})
    hit = ScoredChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        collection_id=uuid.uuid4(),
        score=1.0,
    )
    assert merge_groups([[hit]])[0].chunk_id == hit.chunk_id
    target = SearchTarget(
        collection_id=hit.collection_id, index_version=1, store_collection="memory"
    )
    found, timing = asyncio.run(
        search_targets(
            memory_index(store),
            tenant_id=admin.tenant_id,
            text="desk",
            dense=[0.1] * 1024,
            targets=[target],
            principals=["tenant:*"],
            allowed=["internal"],
            top_k=5,
        )
    )
    assert found == []
    assert timing["store_ms"] >= 0
    assert created["slug"] == "box"
    gateway = TestClient(create_application())
    embedded = gateway.post(
        "/v1/embeddings", json={"input": "desk", "model": "fake-embed", "dimensions": 8}
    )
    assert embedded.status_code == 200
    assert len(embedded.json()["data"][0]["embedding"]) == 8
    ranked = gateway.post("/v1/rerank", json={"query": "desk", "documents": ["desk opens"]})
    assert ranked.status_code == 200
    assert ranked.json()["results"][0]["relevance_score"] > 0


def test_runtime_reexports_and_system_worker_when_temporal_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_runtime.context import assembler, blocks, budget
    from ar_system.worker import run_worker

    assert assembler.build_prompt and blocks and budget

    async def _down(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("temporal is down")

    async def _stop(_seconds: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr("ar_system.worker.Client.connect", _down)
    monkeypatch.setattr("ar_system.worker.asyncio.sleep", _stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_worker())

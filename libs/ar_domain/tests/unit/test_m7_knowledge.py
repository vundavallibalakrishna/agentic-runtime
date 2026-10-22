"""Knowledge access, retrieval, ingest and grounding. Spec: docs/03-specs/10-knowledge.md."""

import asyncio
import io
import uuid
import zipfile
from xml.sax.saxutils import escape

import httpx
import pytest
import respx

from ar_common.errors import ArError, ConflictError, NotFoundError, ValidationFailedError
from ar_common.vectors import lexical_score, unit_vector
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.access import can_manage, can_read_document, can_see
from ar_domain.knowledge.acl import (
    allowed_classifications,
    collection_acl,
    map_external,
    principals_for,
)
from ar_domain.knowledge.answer import compose
from ar_domain.knowledge.book import KnowledgeBook
from ar_domain.knowledge.chunker import chunk_markdown
from ar_domain.knowledge.citations import allocate, content_parts, known_indexes
from ar_domain.knowledge.embedder import embed_texts, rerank
from ar_domain.knowledge.fetchers import check, fetch_bytes, list_changes
from ar_domain.knowledge.grounding import (
    apply_grounding,
    cited_indexes,
    max_sentences,
    strip_unknown,
)
from ar_domain.knowledge.parse import ParseError, parse_bytes
from ar_domain.knowledge.pipeline import ingest_document, max_bytes
from ar_domain.knowledge.qdrant_filter import build_filter, hashed_sparse, physical_name
from ar_domain.knowledge.retrieval import answerable, apply_rerank
from ar_domain.knowledge.store import (
    StoreError,
    get_retrieval_store,
    memory_index,
    rrf_fuse,
    supported_dims,
)
from ar_domain.knowledge.store_pgvector import (
    build_hybrid_sql,
    search_preamble,
)
from ar_domain.knowledge.store_types import (
    SUPPORTED_DIMS,
    DeleteFilter,
    HybridQuery,
    SearchTarget,
)
from ar_domain.knowledge.syncing import acl_sync, sync_source
from ar_ingest.activities import bind_store, ingest_document_activity
from ar_ingest.cli import main as ingest_main
from ar_runtime.activities.auto_retrieve_knowledge import auto_retrieve_knowledge
from ar_runtime.activities.auto_retrieve_knowledge import bind_store as bind_runtime

pytestmark = pytest.mark.unit


def _admin(tenant: uuid.UUID | None = None) -> Actor:
    return Actor(
        tenant or uuid.uuid4(),
        uuid.uuid4(),
        PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
    )


def _reader(tenant: uuid.UUID, user: uuid.UUID | None = None) -> Actor:
    return Actor(tenant, user or uuid.uuid4(), frozenset({"knowledge:read"}))


def test_access_model_and_principal_mapping() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    team = uuid.uuid4()
    row = {
        "tenant_id": tenant,
        "visibility": "team",
        "owner_team_id": team,
        "created_by": owner,
    }
    manager = Actor(tenant, owner, frozenset({"knowledge:read"}), team_ids=frozenset({str(team)}))
    outsider = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    assert can_see(manager, row)
    assert can_manage(manager, row)
    assert not can_see(outsider, row)
    private = {**row, "visibility": "private", "created_by": owner}
    assert can_see(Actor(tenant, owner, frozenset({"knowledge:read"})), private)
    stranger = Actor(tenant, uuid.uuid4(), frozenset({"knowledge:read"}))
    assert not can_see(stranger, private)
    assert allowed_classifications("confidential") == ["public", "internal", "confidential"]
    assert principals_for(owner, group_ids=["g"], team_ids=["t"])[0] == f"user:{owner}"
    assert collection_acl(visibility="tenant", owner_team_id=None, created_by=None) == ["tenant:*"]
    mapped, dropped = map_external(
        [
            {"type": "anyone"},
            {"type": "user", "email": "a@dev.local"},
            {"type": "group", "id": "finance"},
            {"type": "domain", "id": "other.example"},
            {"type": "user", "email": "missing@dev.local"},
        ],
        email_to_user={"a@dev.local": str(owner)},
        group_keys={"finance": "g1"},
        company_domains={"dev.local"},
    )
    assert "tenant:*" in mapped and f"user:{owner}" in mapped and "group:g1" in mapped
    assert dropped == 2
    store = ChatService()
    store.user_groups[owner] = ["g1"]
    store.user_clearance[owner] = "restricted"
    document = {"status": "indexed", "classification": "internal", "acl_principals": ["tenant:*"]}
    assert can_read_document(store, manager, document, row)
    document["acl_principals"] = []
    assert not can_read_document(store, manager, document, row)


def test_sql_builder_always_filters_and_rrf_breaks_ties() -> None:
    for dims in sorted(SUPPORTED_DIMS):
        for config in ("simple", "english"):
            sql = build_hybrid_sql(dims=dims, configs=[config, "nope"])
            assert "ce.tenant_id = :tenant_id" in sql
            assert "ce.acl && CAST(:principals AS text[])" in sql
            assert "ce.classification = ANY(CAST(:allowed AS text[]))" in sql
            assert sql.count("ce.tenant_id = :tenant_id") >= 2
            assert f"halfvec({dims})" in sql
            assert f"websearch_to_tsquery('{config}'" in sql
    with pytest.raises(Exception, match="unsupported_embedding_dims"):
        build_hybrid_sql(dims=12, configs=["simple"])
    assert "hnsw.iterative_scan" in search_preamble(0)[1]
    left = uuid.UUID("00000000-0000-0000-0000-000000000001")
    right = uuid.UUID("00000000-0000-0000-0000-000000000002")
    fused = rrf_fuse(
        [(str(right), 1), (str(left), 1)],
        [(str(left), 1), (str(right), 1)],
        {str(left): (str(left), str(left)), str(right): (str(right), str(right))},
        rrf_k=60,
        fused_k=2,
    )
    assert fused[0].chunk_id == left
    assert fused[0].score == pytest.approx(fused[1].score)
    assert answerable([{"rerank_score": 0.1}], min_score=0.2) is False
    kept, _elapsed, warning = apply_rerank(
        "desk", [{"snippet": "desk opens", "chunk_id": "a"}], top_k=1
    )
    assert kept and warning is None
    assert supported_dims() == SUPPORTED_DIMS
    assert get_retrieval_store("pgvector").backend == "pgvector"
    with pytest.raises(StoreError):
        get_retrieval_store("missing")


def test_chunk_parse_ground_and_cite(monkeypatch: pytest.MonkeyPatch) -> None:
    markdown = "\n".join(
        [
            "# Guide",
            "The visitor desk opens at 08:30.",
            "## Hours",
            "| Day | Open |",
            "| --- | --- |",
            "| Mon | 08:30 |",
            "```",
            "print('badge')",
            "```",
            "<!-- page:2 -->",
            "Token ZX-4471 is on the badge.",
        ]
    )
    chunks = chunk_markdown(markdown, target_tokens=128)
    assert chunks[0].heading_path == ["Guide"]
    assert any("|" in chunk.text for chunk in chunks)
    assert any(chunk.page_from == 2 for chunk in chunks)
    parsed = parse_bytes(
        b"# Title\n\nHello", mime_type="text/markdown", name="a.md", max_bytes=1000
    )
    assert "Title" in parsed
    html = parse_bytes(
        b"<h1>Hi</h1><script>no</script><p>Yes</p>",
        mime_type="text/html",
        name="a.html",
        max_bytes=1000,
    )
    assert "Hi" in html and "no" not in html
    csv = parse_bytes(b"a,b\n1,2\n", mime_type="text/csv", name="a.csv", max_bytes=1000)
    assert "| a | b |" in csv
    docx = _docx(b"Payroll is released on the 28th.")
    assert "Payroll" in parse_bytes(
        docx,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        name="a.docx",
        max_bytes=1000,
    )
    pdf = b"BT (Visitor desk) Tj ET"
    assert "Visitor desk" in parse_bytes(
        pdf, mime_type="application/pdf", name="a.pdf", max_bytes=1000
    )
    with pytest.raises(ParseError):
        parse_bytes(b"x" * 20, mime_type="text/plain", name="a.txt", max_bytes=4)
    monkeypatch.setenv("AR_GROUNDING_MAX_SENTENCES", "1")
    assert max_sentences() == 1
    text = "The desk opens at 08:30 [1]. Payroll is on the 28th [2]. What time is it?"
    strict, report = apply_grounding(text, {1}, mode="strict")
    assert "08:30" in strict and "Payroll" not in strict and report is not None
    monkeypatch.setenv("AR_GROUNDING_MAX_SENTENCES", "200")
    preferred, preferred_report = apply_grounding(text, {1}, mode="preferred")
    assert "Payroll" in preferred
    assert preferred_report is not None
    assert any(claim["status"] == "flagged" for claim in preferred_report["claims"])
    off, empty = apply_grounding(text + " [9]", {1}, mode="off")
    assert empty is None and "[9]" not in off
    citations = allocate(
        [
            {
                "title": "Guide",
                "document_id": "d",
                "chunk_id": "c",
                "collection_id": "k",
                "snippet": "desk",
            },
            {"source_kind": "evidence_item", "evidence_id": "e", "title": "Note", "snippet": "n"},
        ]
    )
    assert citations[0]["index"] == 1 and citations[1]["source_kind"] == "evidence_item"
    assert content_parts("desk [1]", citations)[1]["type"] == "citation_ref"
    assert strip_unknown("see [3]", {1}) == "see "
    assert cited_indexes("a [1] b [2]") == [1, 2]
    assert 1 in known_indexes(citations)
    assert lexical_score("visitor desk", "the visitor desk opens") > 0


def test_collection_acl_search_and_delete_at_source() -> None:
    store = ChatService()
    admin = _admin(demo_id("tenant"))
    member = _reader(demo_id("tenant"), demo_id("member"))
    store.user_emails[admin.user_id] = "admin@dev.local"
    store.user_emails[member.user_id] = "member@dev.local"
    store.company_domains = {"dev.local"}
    book = KnowledgeBook(store)
    with pytest.raises(ArError):
        book.create_collection(member, {"slug": "nope", "name": "Nope"})
    created = book.create_collection(
        admin,
        {"slug": "library", "name": "Library", "description": "Handbooks"},
    )
    collection_id = uuid.UUID(str(created["id"]))
    source = book.create_source(
        admin,
        collection_id,
        {
            "name": "SharePoint",
            "kind": "sharepoint",
            "config": {
                "items": [
                    {
                        "external_id": "guide",
                        "title": "Visitor guide",
                        "uri": "sharepoint://guide",
                        "text": "The visitor desk opens at 08:30. Token ZX-4471.",
                        "acl": [{"type": "anyone"}],
                    },
                    {
                        "external_id": "pay",
                        "title": "Payroll calendar",
                        "uri": "sharepoint://pay",
                        "text": "Payroll is released on the 28th.",
                        "acl": [{"type": "user", "email": "admin@dev.local"}],
                    },
                ]
            },
        },
    )
    admin_hits = book.search(
        admin, {"query": "When is payroll released?", "collection_ids": [collection_id]}
    )
    member_hits = book.search(
        member, {"query": "When is payroll released?", "collection_ids": [collection_id]}
    )
    assert any(hit["title"] == "Payroll calendar" for hit in admin_hits["hits"])
    assert all(hit["title"] != "Payroll calendar" for hit in member_hits["hits"])
    outsider = _admin()
    with pytest.raises(NotFoundError):
        book.get_collection(outsider, collection_id)
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": admin.tenant_id,
        "owner_user_id": admin.user_id,
        "status": "ready",
        "name": "note.md",
        "mime_type": "text/markdown",
    }
    store.blobs[file_id] = b"# Note\n\nBring a badge."
    added = asyncio.run(book.add_documents(admin, collection_id, {"file_ids": [str(file_id)]}))
    document_id = uuid.UUID(str(added["documents"][0]["id"]))
    assert book.chunks(admin, document_id)
    again = ingest_document(store, document_id, store.knowledge_blobs[document_id])
    assert again == "unchanged"
    book.patch_collection(admin, collection_id, {"description": "Updated"})
    book.pause(admin, uuid.UUID(str(source["id"])))
    book.resume(admin, uuid.UUID(str(source["id"])))
    listed = book.list_documents(admin, collection_id, query="Visitor")
    assert any(row["title"] == "Visitor guide" for row in listed)
    source_row = store.knowledge_sources[uuid.UUID(str(source["id"]))]
    source_row["config"] = {"items": [], "deleted_external_ids": ["guide"]}
    sync_source(store, source_row, mode="incremental", actor_id=admin.user_id)
    after = book.search(
        admin, {"query": "ZX-4471", "collection_ids": [collection_id], "debug": True}
    )
    assert all(hit["title"] != "Visitor guide" for hit in after["hits"])
    assert after["debug"]["backend"] == "memory"
    jobs = book.list_jobs(admin, collection_id)
    book.cancel_job(admin, uuid.UUID(str(jobs[-1]["id"])))
    book.remove_document(admin, document_id)
    with pytest.raises(ConflictError):
        book.create_collection(admin, {"slug": "library", "name": "Again"})
    with pytest.raises(ValidationFailedError):
        book.create_collection(admin, {"slug": "bad dims", "name": "Bad"})
    assert max_bytes() >= 1


def test_embedder_connectors_and_activities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_MODEL_GATEWAY_URL", "http://gateway.test")
    vector = unit_vector("desk", 8)
    with respx.mock:
        respx.post("http://gateway.test/v1/embeddings").mock(
            return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": vector}]})
        )
        respx.post("http://gateway.test/v1/rerank").mock(
            return_value=httpx.Response(
                200, json={"results": [{"index": 0, "relevance_score": 0.9}]}
            )
        )
        assert embed_texts(["desk"], model="fake-embed", dimensions=8) == [vector]
        assert rerank("desk", ["desk opens"]) == [0.9]
    page = list_changes(
        {"kind": "database", "config": {"rows": [{"id": "1", "title": "Row", "text": "hello"}]}},
        mode="full",
    )
    assert page["items"][0]["external_id"] == "1"
    web = list_changes(
        {"kind": "web", "config": {"items": [{"external_id": "p", "title": "Page"}]}},
        mode="incremental",
    )
    assert web["items"][0]["external_id"] == "p"
    assert check({"kind": "web", "config": {"items": [{"external_id": "p", "title": "Page"}]}})[
        "ok"
    ]
    raw, mime = fetch_bytes({"text": "hello", "mime_type": "text/plain"})
    assert raw == b"hello" and mime == "text/plain"
    name = physical_name(
        isolation_tier="dedicated", tenant_short="Dev Local", model_key="embed", dims=1024
    )
    assert name.startswith("ar_kn_t_")
    query = HybridQuery(
        tenant_id=uuid.uuid4(),
        text="desk",
        dense=[0.1, 0.2],
        targets=[
            SearchTarget(collection_id=uuid.uuid4(), index_version=1, store_collection="pg:1024")
        ],
        principals=["tenant:*"] * 501,
        allowed_classifications=["internal"],
    )
    filt = build_filter(query)
    assert "should" in str(filt)
    assert hashed_sparse("ZX-4471")[0]
    store = ChatService()
    admin = _admin()
    book = KnowledgeBook(store)
    created = book.create_collection(admin, {"slug": "box", "name": "Box"})
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "tenant_id": admin.tenant_id,
        "owner_user_id": admin.user_id,
        "status": "ready",
        "name": "a.md",
        "mime_type": "text/markdown",
    }
    store.blobs[file_id] = b"The visitor desk opens at 08:30."
    added = asyncio.run(
        book.add_documents(admin, uuid.UUID(str(created["id"])), {"file_ids": [str(file_id)]})
    )
    bind_store(store)
    status = asyncio.run(
        ingest_document_activity(
            {"document_id": added["documents"][0]["id"], "actor_id": str(admin.user_id)}
        )
    )
    assert status["status"] in {"indexed", "unchanged"}
    bind_runtime(store)
    empty = asyncio.run(auto_retrieve_knowledge({"question": "hi"}))
    assert empty["citations"] == []
    captured: list[str] = []
    monkeypatch.setattr("builtins.print", captured.append)
    ingest_main(
        ["migrate-store", "--collection-id", str(created["id"]), "--target", "qdrant", "--dry-run"]
    )
    assert "dry_run" in captured[0]
    index = memory_index(store)
    assert asyncio.run(index.health()).ok
    with pytest.raises(ValueError):
        DeleteFilter(tenant_id=admin.tenant_id)


def test_librarian_answers_only_from_readable_documents() -> None:
    store = ChatService()
    store.seed_demo()
    store.seed_showcase()
    from ar_domain.knowledge.answer import compose as compose_answer

    agent = next(row for row in store.agents.values() if row.get("slug") == "librarian")
    version = next(row for row in store.versions.values() if row.get("agent_id") == agent["id"])
    run = {
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("member"),
        "agent_version_id": version["id"],
    }
    store.user_roles[demo_id("member")] = {"member"}
    composed = compose_answer(store, run, "When is payroll released?")
    assert composed is not None
    assert "Payroll" not in str(composed["text"]) or "28th" not in str(composed["text"])
    titles = [item.get("title") for item in composed["citations"]]
    assert "Payroll calendar" not in titles
    admin_run = {**run, "user_id": demo_id("admin")}
    store.user_roles[demo_id("admin")] = {"tenant_admin"}
    admin = compose(store, admin_run, "When is payroll released?")
    assert admin is not None
    assert any(item.get("title") == "Payroll calendar" for item in admin["citations"])


def test_acl_sync_does_not_require_reembed() -> None:
    store = ChatService()
    admin = _admin(demo_id("tenant"))
    store.user_emails[admin.user_id] = "admin@dev.local"
    store.company_domains = {"dev.local"}
    book = KnowledgeBook(store)
    created = book.create_collection(admin, {"slug": "acl", "name": "ACL", "sensitivity": "high"})
    source = book.create_source(
        admin,
        uuid.UUID(str(created["id"])),
        {
            "name": "Drive",
            "kind": "google_drive",
            "config": {
                "items": [
                    {
                        "external_id": "doc",
                        "title": "Roster",
                        "text": "Dev Member is on call.",
                        "acl": [{"type": "user", "email": "admin@dev.local"}],
                    }
                ]
            },
        },
    )
    row = store.knowledge_sources[uuid.UUID(str(source["id"]))]
    row["config"] = {
        "items": [
            {
                "external_id": "doc",
                "title": "Roster",
                "acl": [{"type": "anyone"}],
            }
        ]
    }
    job = acl_sync(store, row, actor_id=admin.user_id)
    assert job["status"] in {"succeeded", "partially_failed"}
    document = next(iter(store.knowledge_documents.values()))
    assert "tenant:*" in document["acl_principals"]


def _docx(paragraph: bytes) -> bytes:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{escape(paragraph.decode())}</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("word/document.xml", document)
    return buffer.getvalue()

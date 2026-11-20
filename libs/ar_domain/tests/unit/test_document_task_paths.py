"""Paths the document-task modules take once a turn names a file."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest

from ar_common.errors import ArError, NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.documents.binding import bind_turn, context_window_for, remember_task
from ar_domain.documents.lifecycle import (
    delete_file_cascade,
    delete_library,
    reprocess,
    sweep_expired,
)
from ar_domain.documents.planner import model_ask
from ar_domain.documents.sections import next_batch, reading_part, review_part, run_section
from ar_domain.documents.strategy import ReadingPlan
from ar_domain.files.clamav import instream
from ar_domain.knowledge.uploads import ensure_uploads, find_uploads, is_system
from ar_domain.runs.request import asked


class _Store:
    def __init__(self) -> None:
        self.files: dict[object, dict[str, object]] = {}
        self.library_documents: dict[object, dict[str, object]] = {}
        self.knowledge_documents: dict[object, dict[str, object]] = {}
        self.knowledge_collections: dict[object, dict[str, object]] = {}
        self.conversations: dict[object, dict[str, object]] = {}
        self.document_chunks: dict[object, dict[str, object]] = {}
        self.domain_events: list[object] = []
        self.audit_log: list[object] = []
        self.originals: dict[str, bytes] = {}
        self.blobs: dict[object, bytes] = {}
        self.runs: dict[object, dict[str, object]] = {}
        self.versions: dict[object, dict[str, object]] = {}


def test_bind_turn_plans_and_remembers_the_reading() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    file_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    store = _Store()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "status": "ready",
        "sha256": "abc",
        "size_bytes": 12,
        "filename": "note.md",
    }
    store.library_documents[uuid.uuid4()] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "content_hash": "abc",
        "status": "ready",
        "title": "Note",
        "page_count": 1,
        "passages": [{"heading": "Hours", "page": 1, "text": "Opens at eight."}],
    }
    store.knowledge_collections[collection_id] = {
        "id": collection_id,
        "tenant_id": tenant,
        "visibility": "tenant",
        "acl_principals": ["tenant:*"],
    }
    seen: dict[str, str] = {}

    def ask(task: str, evidence: str) -> str:
        seen["task"] = task
        seen["evidence"] = evidence
        return '{"coverage":"whole","scope":"perDocument","outputShape":"note","steps":["read"]}'

    files, plan, items, schema, text = bind_turn(
        store,
        tenant_id=tenant,
        user_id=owner,
        attachment_ids=[file_id, file_id],
        file_ids=[file_id],
        collection_ids=[collection_id],
        instruction="Outline it.",
        task_template="outline",
        strategy="",
        items=[],
        response_format=None,
        context_window=32_768,
        definition={
            "task_templates": [
                {
                    "id": "outline",
                    "prompt": "Outline each document.",
                    "items": ["hours"],
                    "output_schema": {"type": "object"},
                }
            ]
        },
        ask=ask,
    )
    assert files == [file_id]
    assert plan.strategy == "full"
    assert plan.template_id == "outline"
    assert text.startswith("Outline each document.")
    assert schema == {"type": "object"}
    assert "Hours" in seen["evidence"]
    run: dict[str, object] = {"id": uuid.uuid4(), "request": {}}
    remember_task(
        store,
        run,
        tenant_id=tenant,
        user_id=owner,
        file_ids=files,
        collection_ids=[collection_id],
        items=items,
        plan=plan,
    )
    assert asked(run, "strategy") == "full"
    assert asked(run, "task_template") == "outline"
    assert store.audit_log


def test_bind_turn_rejects_a_missing_unready_or_failed_file() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    store = _Store()
    missing = uuid.uuid4()
    with pytest.raises(NotFoundError):
        bind_turn(
            store,
            tenant_id=tenant,
            user_id=owner,
            attachment_ids=[missing],
            file_ids=[],
            collection_ids=[],
            instruction="Read it.",
            task_template="",
            strategy="",
            items=[],
            response_format=None,
            context_window=None,
            definition=None,
            ask=None,
        )
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "status": "pending",
        "sha256": "abc",
    }
    with pytest.raises(ArError):
        bind_turn(
            store,
            tenant_id=tenant,
            user_id=owner,
            attachment_ids=[file_id],
            file_ids=[],
            collection_ids=[],
            instruction="Read it.",
            task_template="",
            strategy="",
            items=[],
            response_format=None,
            context_window=None,
            definition=None,
            ask=None,
        )
    store.files[file_id]["status"] = "ready"
    store.library_documents[uuid.uuid4()] = {
        "tenant_id": tenant,
        "content_hash": "abc",
        "status": "failed",
        "error_code": "text_not_extracted",
    }
    with pytest.raises(ArError):
        bind_turn(
            store,
            tenant_id=tenant,
            user_id=owner,
            attachment_ids=[file_id],
            file_ids=[],
            collection_ids=[],
            instruction="Read it.",
            task_template="",
            strategy="",
            items=[],
            response_format=None,
            context_window=None,
            definition=None,
            ask=None,
        )


def test_a_stranger_cannot_name_the_file_and_too_many_collections_fail() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    stranger = uuid.uuid4()
    file_id = uuid.uuid4()
    store = _Store()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "status": "ready",
        "sha256": "abc",
    }
    with pytest.raises(NotFoundError):
        bind_turn(
            store,
            tenant_id=tenant,
            user_id=stranger,
            attachment_ids=[file_id],
            file_ids=[],
            collection_ids=[],
            instruction="Read it.",
            task_template="",
            strategy="",
            items=[],
            response_format=None,
            context_window=None,
            definition=None,
            ask=None,
        )
    with pytest.raises(ArError):
        bind_turn(
            store,
            tenant_id=tenant,
            user_id=owner,
            attachment_ids=[],
            file_ids=[],
            collection_ids=[uuid.uuid4() for _ in range(21)],
            instruction="Read it.",
            task_template="",
            strategy="",
            items=[],
            response_format=None,
            context_window=None,
            definition=None,
            ask=None,
        )


def test_delete_reprocess_and_the_retention_sweep() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    actor = Actor(tenant, owner, frozenset({"chat:use"}))
    document_id = uuid.uuid4()
    file_id = uuid.uuid4()
    store = _Store()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "content_hash": "abc",
        "status": "ready",
        "title": "Note",
        "filename": "note.md",
        "media_type": "text/markdown",
        "object_key": "library/note",
        "passages": [],
        "tables": [],
        "metadata": {},
    }
    store.originals["library/note"] = b"# Hours\n\nThe desk opens at eight.\n"
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "sha256": "abc",
        "status": "ready",
        "retention_until": "2000-01-01T00:00:00+00:00",
    }
    store.blobs[file_id] = b"bytes"
    view = reprocess(store, actor, document_id)
    assert view["status"] == "ready"
    assert store.library_documents[document_id]["passages"]
    removed = sweep_expired(store, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert removed == 1
    assert document_id not in store.library_documents
    assert sweep_expired(object()) == 0


def test_a_second_file_keeps_the_extraction() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    digest = "same"
    first = uuid.uuid4()
    second = uuid.uuid4()
    document_id = uuid.uuid4()
    store = _Store()
    row = {
        "tenant_id": tenant,
        "owner_user_id": owner,
        "sha256": digest,
        "status": "ready",
        "deleted_at": None,
    }
    store.files[first] = {**row, "id": first}
    store.files[second] = {**row, "id": second}
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "content_hash": digest,
        "status": "ready",
    }
    delete_file_cascade(store, tenant, owner, store.files[first])
    assert document_id in store.library_documents
    store.files[first]["deleted_at"] = datetime(2026, 1, 1, tzinfo=UTC)
    delete_file_cascade(store, tenant, owner, store.files[second])
    assert document_id not in store.library_documents


def test_sections_report_the_plan_and_reduce_across_documents() -> None:
    run: dict[str, object] = {"id": uuid.uuid4(), "request": {}}
    assert next_batch(_Store(), run) is None
    assert reading_part(run) is None
    from ar_domain.runs.request import ask

    ask(run, "strategy", "map_reduce")
    ask(
        run,
        "plan",
        {
            "coverage": "whole",
            "scope": "acrossDocuments",
            "outputShape": "changes",
            "source": "model",
        },
    )
    note = reading_part(run)
    assert note is not None and note["strategy"] == "mapReduce"
    run["checkpoint"] = {
        "document_task": {
            "sections": [
                {
                    "fileId": "left",
                    "anchor": "p1-s0",
                    "page": 1,
                    "heading": "Hours",
                    "text": "Opens at eight.",
                },
                {
                    "fileId": "right",
                    "anchor": "p1-s0",
                    "page": 1,
                    "heading": "Hours",
                    "text": "Opens at nine.",
                },
            ],
            "done": {},
            "reduced": False,
        }
    }
    store = _Store()
    store.runs[run["id"]] = run
    pending = next_batch(store, run)
    assert pending is not None and len(pending) == 2
    run_section(store, run, pending[0])
    run_section(store, run, pending[1])
    assert next_batch(store, run) is None
    review = review_part(run)
    assert review is not None and review["rows"]


def test_the_planner_uses_the_tenant_model_when_one_is_wired() -> None:
    tenant = uuid.uuid4()
    conversation_id = uuid.uuid4()
    store = _Store()
    store.conversations[conversation_id] = {"model_alias": "reasoning"}
    assert model_ask(store, "not-a-uuid", {}) is None
    ask = model_ask(store, tenant, {"conversation_id": conversation_id})
    assert ask is not None
    assert ask("plan", "evidence") is None
    assert model_ask(object(), tenant, {}) is None


def test_uploads_collection_is_found_or_left_alone() -> None:
    tenant = uuid.uuid4()
    actor = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    assert is_system({"stats": {"system": "uploads"}})
    assert not is_system({})
    store = _Store()
    assert find_uploads(store, tenant) is None
    taken = uuid.uuid4()
    store.knowledge_collections[taken] = {
        "id": taken,
        "tenant_id": tenant,
        "slug": "uploads",
        "stats": {},
    }
    assert ensure_uploads(store, actor) is None
    store.knowledge_collections[taken]["stats"] = {"system": "uploads"}
    assert find_uploads(store, tenant) is not None


def test_clamav_rejects_a_bad_address_and_reports_a_finding() -> None:
    import socket
    import threading

    assert instream(b"hello", "not-an-address", timeout_s=1) == "error"
    assert instream(b"hello", "./missing-clamd.sock", timeout_s=1) == "error"
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        conn, _addr = server.accept()
        conn.settimeout(2)
        try:
            chunks: list[bytes] = []
            while True:
                try:
                    piece = conn.recv(65536)
                except TimeoutError:
                    break
                if not piece:
                    break
                chunks.append(piece)
                if b"\x00\x00\x00\x00" in b"".join(chunks):
                    break
            conn.sendall(b"stream: Eicar FOUND\0")
        finally:
            conn.close()
            server.close()

    threading.Thread(target=serve, daemon=True).start()
    assert instream(b"x" * 70_000, f"127.0.0.1:{port}", timeout_s=2) == "infected"


def test_a_section_activity_stores_the_result() -> None:
    from ar_runtime.activities.document_section import document_section
    from ar_runtime.activities.expire_approval import bind_store

    store = _Store()
    run_id = uuid.uuid4()
    run = {
        "id": run_id,
        "tenant_id": uuid.uuid4(),
        "checkpoint": {
            "document_task": {
                "sections": [
                    {
                        "fileId": "file-1",
                        "anchor": "p1-s0",
                        "page": 1,
                        "heading": "Hours",
                        "text": "The desk opens at eight.",
                    }
                ],
                "done": {},
                "reduced": False,
            }
        },
        "request": {"strategy": "map_reduce"},
    }
    store.runs[run_id] = run
    bind_store(store)
    section = {"fileId": "file-1", "anchor": "p1-s0"}
    result = asyncio.run(document_section({"run_id": str(run_id), "section": section}))
    assert result["status"] == "ok"
    assert result["anchor"] == "p1-s0"
    missing = asyncio.run(document_section({"run_id": str(uuid.uuid4())}))
    assert missing["status"] == "missing"


def test_delete_library_hides_a_row_the_caller_does_not_own() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    document_id = uuid.uuid4()
    store = _Store()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "content_hash": "abc",
        "status": "ready",
    }
    delete_library(store, Actor(tenant, owner, frozenset({"chat:use"})), document_id)
    assert document_id not in store.library_documents
    with pytest.raises(NotFoundError):
        delete_library(store, Actor(tenant, uuid.uuid4(), frozenset({"chat:use"})), document_id)


def test_deleting_the_library_row_drops_the_indexed_copy() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    document_id = uuid.uuid4()
    knowledge_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    file_id = uuid.uuid4()
    store = _Store()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "sha256": "abc",
        "status": "ready",
    }
    store.knowledge_collections[collection_id] = {
        "id": collection_id,
        "tenant_id": tenant,
        "store_collection": "memory",
    }
    store.knowledge_documents[knowledge_id] = {
        "id": knowledge_id,
        "tenant_id": tenant,
        "collection_id": collection_id,
        "raw_file_id": file_id,
        "version_hash": "abc",
        "status": "indexed",
    }
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "content_hash": "abc",
        "status": "ready",
        "object_key": "",
        "filename": "note.md",
    }
    delete_library(store, Actor(tenant, owner, frozenset({"chat:use"})), document_id)
    assert store.knowledge_documents[knowledge_id]["status"] == "deleted"
    kept = uuid.uuid4()
    store.files[kept] = {
        "id": kept,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "status": "ready",
        "retention_until": "2999-01-01T00:00:00+00:00",
    }
    assert sweep_expired(store, now=datetime(2026, 1, 1, tzinfo=UTC)) == 0
    with pytest.raises(NotFoundError):
        reprocess(store, Actor(tenant, uuid.uuid4(), frozenset({"chat:use"})), uuid.uuid4())


def test_a_reader_of_the_collection_may_name_the_file() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    reader = uuid.uuid4()
    file_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    knowledge_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    store = _Store()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "status": "ready",
        "sha256": "abc",
        "conversation_id": conversation_id,
    }
    store.conversations[conversation_id] = {"tenant_id": tenant, "user_id": reader}
    store.knowledge_collections[collection_id] = {"id": collection_id, "tenant_id": tenant}
    store.knowledge_documents[knowledge_id] = {
        "id": knowledge_id,
        "tenant_id": tenant,
        "collection_id": collection_id,
        "raw_file_id": file_id,
        "status": "indexed",
        "classification": "internal",
        "acl_principals": [f"user:{reader}"],
    }
    files, plan, _items, _schema, _text = bind_turn(
        store,
        tenant_id=tenant,
        user_id=reader,
        attachment_ids=[file_id],
        file_ids=[],
        collection_ids=[],
        instruction="Read it.",
        task_template="",
        strategy="",
        items=[],
        response_format=None,
        context_window=None,
        definition=None,
        ask=None,
    )
    assert files == [file_id]
    assert plan.strategy in {"full", "map_reduce"}


def test_the_uploads_collection_is_not_created_without_an_embedding_model() -> None:
    tenant = uuid.uuid4()
    actor = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    assert ensure_uploads(_Store(), actor) is None


def test_map_reduce_reads_sections_from_the_attached_file() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    conversation_id = uuid.uuid4()
    file_id = uuid.uuid4()
    document_id = uuid.uuid4()
    message_id = uuid.uuid4()
    store = _Store()
    store.messages = {  # type: ignore[attr-defined]
        message_id: {
            "id": message_id,
            "tenant_id": tenant,
            "conversation_id": conversation_id,
            "role": "user",
            "is_active_branch": True,
            "created_at": "2026-01-01T00:00:00+00:00",
            "content": [{"type": "file", "file_id": str(file_id)}],
        }
    }
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "sha256": "abc",
        "name": "note.md",
        "mime_type": "text/markdown",
        "size_bytes": 20,
        "status": "ready",
    }
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "content_hash": "abc",
        "passages": [{"anchor": "p1-s0", "page": 1, "heading": "Hours", "text": "Opens at eight."}],
    }
    run: dict[str, object] = {
        "id": uuid.uuid4(),
        "conversation_id": conversation_id,
        "request": {"strategy": "map_reduce"},
        "checkpoint": {"document_task": {"sections": [], "done": [], "reduced": False}},
    }
    assert next_batch(store, run) is None
    run.pop("checkpoint")
    pending = next_batch(store, run)
    assert pending is not None and pending[0]["anchor"] == "p1-s0"
    other = uuid.uuid4()
    store.files[other] = {"id": other, "tenant_id": tenant, "sha256": "nope"}
    store.knowledge_documents[uuid.uuid4()] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "version_hash": "other",
        "raw_file_id": other,
        "status": "indexed",
    }
    store.library_documents[document_id]["owner_user_id"] = owner
    store.library_documents[document_id]["filename"] = "note.md"
    store.library_documents[document_id]["media_type"] = "text/markdown"
    store.library_documents[document_id]["object_key"] = "library/note"
    store.library_documents[document_id]["status"] = "ready"
    store.originals["library/note"] = b"# Hours\n\nThe desk opens at eight.\n"
    reprocess(store, Actor(tenant, owner, frozenset({"chat:use"})), document_id)


def test_the_remaining_guards_on_delete_and_a_section() -> None:
    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    store = _Store()
    file_id = uuid.uuid4()
    store.files[file_id] = {"id": file_id, "tenant_id": tenant, "sha256": "", "status": "ready"}
    delete_file_cascade(store, tenant, owner, store.files[file_id])
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": "not-a-uuid",
        "owner_user_id": owner,
        "status": "ready",
        "retention_until": "2000-01-01T00:00:00+00:00",
    }
    assert sweep_expired(store, now=datetime(2026, 1, 1, tzinfo=UTC)) == 0
    document_id = uuid.uuid4()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "content_hash": "abc",
        "status": "ready",
        "filename": "note.md",
        "object_key": "missing",
    }
    with pytest.raises(NotFoundError):
        reprocess(store, Actor(tenant, owner, frozenset({"chat:use"})), document_id)
    run: dict[str, object] = {
        "id": uuid.uuid4(),
        "checkpoint": {
            "document_task": {
                "sections": [{"fileId": "f", "anchor": "a", "text": ""}],
                "done": [],
                "reduced": False,
            }
        },
    }
    assert run_section(store, run, {"fileId": "f", "anchor": "a"})["quote"] == ""


def test_context_window_is_missing_without_a_registered_model() -> None:
    assert context_window_for(_Store(), uuid.uuid4(), {}) is None
    plan = ReadingPlan(
        strategy="full",
        reason="",
        usable_tokens=1,
        fits=True,
        coverage="whole",
        scope="perDocument",
        output_shape="",
        steps=(),
        source="fallback",
    )
    assert plan.strategy == "full"

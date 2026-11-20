"""Document tasks: naming files on a turn, reading by section, and what a delete removes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ar_common.errors import ArError, NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.documents.binding import bind_turn, context_window_for, remember_task
from ar_domain.documents.library import DocumentLibrary
from ar_domain.documents.lifecycle import (
    delete_file_cascade,
    delete_library,
    reprocess,
    sweep_expired,
)
from ar_domain.documents.sections import (
    begin_map,
    deliver_map,
    run_pending,
    run_section,
    tools_part,
)
from ar_domain.knowledge.uploads import SLUG, ensure_uploads, find_uploads, is_system
from ar_domain.runs.request import asked
from ar_testing.demo import demo_store


class _Store:
    """The dictionaries these functions read, and nothing else."""

    def __init__(self) -> None:
        self.scanner = "none"
        self.audit_log: list[dict[str, object]] = []
        self.files: dict[uuid.UUID, dict[str, object]] = {}
        self.blobs: dict[uuid.UUID, bytes] = {}
        self.library_documents: dict[uuid.UUID, dict[str, object]] = {}
        self.knowledge_collections: dict[uuid.UUID, dict[str, object]] = {}
        self.knowledge_documents: dict[uuid.UUID, dict[str, object]] = {}
        self.conversations: dict[uuid.UUID, dict[str, object]] = {}
        self.messages: dict[uuid.UUID, dict[str, object]] = {}
        self.runs: dict[object, dict[str, object]] = {}
        self.job_progress: dict[object, dict[str, object]] = {}


def _file(
    store: _Store,
    tenant: uuid.UUID,
    owner: uuid.UUID | None,
    digest: str,
    **more: object,
) -> uuid.UUID:
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "sha256": digest,
        "status": "ready",
        "filename": f"{digest}.md",
        "size_bytes": 120,
        "deleted_at": None,
        **more,
    }
    return file_id


def _library(
    store: _Store, tenant: uuid.UUID, owner: uuid.UUID, digest: str, **more: object
) -> uuid.UUID:
    document_id = uuid.uuid4()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": owner,
        "content_hash": digest,
        "status": "ready",
        "title": f"Title of {digest}",
        "filename": f"{digest}.md",
        "passages": [
            {"anchor": "p1-s0", "page": 1, "heading": "Hours", "text": "The desk opens at eight."},
            {"anchor": "p2-s0", "page": 2, "heading": "Badges", "text": "A badge lasts a day."},
            "not a passage",
        ],
        **more,
    }
    return document_id


def _bind(store: _Store, tenant: uuid.UUID, user: uuid.UUID, **more: object) -> tuple:
    arguments: dict[str, object] = {
        "attachment_ids": [],
        "file_ids": [],
        "collection_ids": [],
        "instruction": "Summarise the file.",
        "task_template": "",
        "items": [],
        "response_format": None,
        "context_window": 32_768,
        "definition": None,
        **more,
    }
    return bind_turn(store, tenant_id=tenant, user_id=user, **arguments)  # type: ignore[arg-type]


def test_a_turn_names_its_files_once_and_plans_from_what_they_hold() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    file_id = _file(store, tenant, user, "one")
    _library(store, tenant, user, "one", page_count=7)
    bare = _file(store, tenant, user, "bare")
    files, named, items, schema, text = _bind(
        store, tenant, user, attachment_ids=[file_id, bare], file_ids=[file_id]
    )
    assert files == [file_id, bare]
    assert named[0].file_id == str(file_id)
    assert named[0].page_count == 7
    assert (items, schema, text) == ([], None, "Summarise the file.")


def test_a_file_the_caller_may_not_use_is_not_found() -> None:
    store = _Store()
    tenant, user, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, file_ids=[uuid.uuid4()])
    elsewhere = _file(store, uuid.uuid4(), user, "elsewhere")
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, file_ids=[elsewhere])
    gone = _file(store, tenant, user, "gone", deleted_at=datetime.now(UTC))
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, file_ids=[gone])
    theirs = _file(store, tenant, other, "theirs")
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, file_ids=[theirs])


def test_a_file_reaches_a_reader_through_a_conversation_or_a_collection() -> None:
    store = _Store()
    tenant, user, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    conversation = uuid.uuid4()
    store.conversations[conversation] = {"id": conversation, "tenant_id": tenant, "user_id": user}
    in_chat = _file(store, tenant, other, "chat", conversation_id=conversation)
    assert _bind(store, tenant, user, file_ids=[in_chat])[0] == [in_chat]
    foreign = uuid.uuid4()
    store.conversations[foreign] = {"id": foreign, "tenant_id": uuid.uuid4(), "user_id": user}
    not_mine = _file(store, tenant, other, "foreign", conversation_id=foreign)
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, file_ids=[not_mine])

    shared = _file(store, tenant, other, "shared")
    collection = uuid.uuid4()
    store.knowledge_collections[collection] = {"id": collection, "tenant_id": tenant}
    for status, readers in (("deleted", [f"user:{user}"]), ("indexed", [f"user:{user}"])):
        knowledge = uuid.uuid4()
        store.knowledge_documents[knowledge] = {
            "id": knowledge,
            "tenant_id": tenant,
            "collection_id": collection,
            "raw_file_id": shared,
            "status": status,
            "classification": "internal",
            "acl_principals": readers,
        }
    assert _bind(store, tenant, user, file_ids=[shared])[0] == [shared]


def test_a_file_that_is_not_ready_or_could_not_be_read_is_refused_in_words() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    scanning = _file(store, tenant, user, "scanning", status="scanning")
    with pytest.raises(ArError) as waiting:
        _bind(store, tenant, user, file_ids=[scanning])
    assert "not ready" in str(waiting.value)
    unread = _file(store, tenant, user, "unread")
    _library(store, tenant, user, "unread", status="failed", error_code="no_text_layer")
    with pytest.raises(ArError) as failed:
        _bind(store, tenant, user, file_ids=[unread])
    assert "no_text_layer" in str(failed.value)


def test_collections_named_on_a_turn_must_exist_and_be_visible() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    seen = uuid.uuid4()
    store.knowledge_collections[seen] = {"id": seen, "tenant_id": tenant, "visibility": "tenant"}
    hidden = uuid.uuid4()
    store.knowledge_collections[hidden] = {
        "id": hidden,
        "tenant_id": tenant,
        "visibility": "private",
        "created_by": uuid.uuid4(),
    }
    assert _bind(store, tenant, user, collection_ids=[seen])[0] == []
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, collection_ids=[hidden])
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, collection_ids=[uuid.uuid4()])
    with pytest.raises(NotFoundError):
        _bind(store, tenant, user, collection_ids=[uuid.uuid4() for _ in range(21)])


def test_a_template_fills_the_request_and_is_named_on_the_plan() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    file_id = _file(store, tenant, user, "one")
    _library(store, tenant, user, "one")
    definition: dict[str, object] = {
        "taskTemplates": [
            {"id": "gaps", "prompt": "List what the file leaves out.", "items": ["Opening hours"]}
        ]
    }
    _files, named, items, _schema, text = _bind(
        store,
        tenant,
        user,
        file_ids=[file_id],
        instruction="Look at the visitor desk.",
        task_template="gaps",
        definition=definition,
    )
    assert text == "List what the file leaves out.\n\nLook at the visitor desk."
    assert items == [{"id": "", "text": "Opening hours"}]
    assert named[0].outline == ("Hours", "Badges")
    assert named[0].page_count == 2


def test_the_turn_request_and_its_audit_row_hold_ids_and_sizes_not_text() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    file_id = _file(store, tenant, user, "one")
    missing = uuid.uuid4()
    collection = uuid.uuid4()
    run: dict[str, object] = {"id": uuid.uuid4(), "tenant_id": tenant}
    remember_task(
        store,
        run,
        tenant_id=tenant,
        user_id=user,
        file_ids=[file_id, missing],
        collection_ids=[collection],
        items=[{"id": "a", "text": "Opening hours"}, "Badges"],
        template_id="gaps",
    )
    assert asked(run, "task_template") == "gaps"
    assert asked(run, "items") == [
        {"id": "a", "text": "Opening hours"},
        {"id": "", "text": "Badges"},
    ]
    assert asked(run, "file_ids") == [str(file_id), str(missing)]
    assert asked(run, "collection_ids") == [str(collection)]
    row = store.audit_log[-1]
    assert row["action"] == "document_task.started"
    detail = row["detail"]
    assert isinstance(detail, dict)
    assert detail["bytes"] == [
        {"fileId": str(file_id), "bytes": 120},
        {"fileId": str(missing), "bytes": 0},
    ]
    assert "Opening hours" not in str(row)
    assert context_window_for(store, tenant, run) is None


def _conversation(store: _Store, tenant: uuid.UUID, files: list[uuid.UUID]) -> uuid.UUID:
    conversation = uuid.uuid4()
    message = uuid.uuid4()
    store.messages[message] = {
        "id": message,
        "tenant_id": tenant,
        "conversation_id": conversation,
        "role": "user",
        "created_at": "2026-11-20T00:00:00Z",
        "content": [{"type": "file", "file_id": str(item)} for item in files],
    }
    return conversation


def _section_run(
    store: _Store, tenant: uuid.UUID, user: uuid.UUID, conversation: uuid.UUID
) -> dict[str, object]:
    run: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation,
    }
    store.runs[run["id"]] = run
    return run


def _read(*args: object) -> str:
    text = str(args[-1])
    return text.split(".", maxsplit=1)[0] if text.strip() else ""


def test_a_long_file_is_read_a_section_at_a_time_and_reduced_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    first = _file(store, tenant, user, "one", name="one.md")
    second = _file(store, tenant, user, "two", name="two.md")
    _library(store, tenant, user, "one")
    _library(store, tenant, user, "two")
    run = _section_run(store, tenant, user, _conversation(store, tenant, [first, second]))
    assert tools_part(run) is None
    monkeypatch.setattr("ar_domain.documents.sections._read_model", _read)
    job = begin_map(
        store,
        run,
        {"instruction": "Say when the desk opens.", "fileIds": [str(first), str(second)]},
    )
    pending = job["sections"]
    assert isinstance(pending, list)
    assert [(item["fileId"], item["anchor"]) for item in pending] == [
        (str(first), "p1-s0"),
        (str(first), "p2-s0"),
        (str(second), "p1-s0"),
        (str(second), "p2-s0"),
    ]
    done = run_section(store, run, pending[0])
    assert done["output"] == "The desk opens at eight"
    run_pending(store, run)
    body = deliver_map(store, run)
    assert "p2-s0 p.2" in str(run["document_reduction"])
    assert len(body["results"]) == 4  # type: ignore[arg-type]


def test_sections_past_the_cap_are_left_unread_and_the_run_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_common.settings import get_settings, set_settings

    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    only = _file(store, tenant, user, "one", name="one.md")
    _library(store, tenant, user, "one")
    run = _section_run(store, tenant, user, _conversation(store, tenant, [only]))
    monkeypatch.setattr("ar_domain.documents.sections._read_model", _read)
    before = get_settings()
    set_settings(before.model_copy(update={"document_section_cap": 1}))
    try:
        begin_map(store, run, {"instruction": "Read the file.", "fileIds": [str(only)]})
        run_pending(store, run)
        deliver_map(store, run)
    finally:
        set_settings(before)
    reduction = str(run["document_reduction"])
    assert "p1-s0" in reduction
    assert "p2-s0" not in reduction
    assert "More sections remain." in reduction


def test_three_files_stay_a_list_of_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    files = [_file(store, tenant, user, name, name=f"{name}.md") for name in ("a", "b", "c")]
    for name in ("a", "b", "c"):
        _library(store, tenant, user, name)
    run = _section_run(store, tenant, user, _conversation(store, tenant, files))
    monkeypatch.setattr("ar_domain.documents.sections._read_model", _read)
    begin_map(
        store,
        run,
        {"instruction": "Read each section.", "fileIds": [str(item) for item in files]},
    )
    run_pending(store, run)
    body = deliver_map(store, run)
    rows = body["results"]
    assert isinstance(rows, list)
    assert len(rows) == 6


def test_deleting_a_file_keeps_the_reading_while_another_file_has_the_same_bytes() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    first = _file(store, tenant, user, "same")
    second = _file(store, tenant, user, "same")
    document = _library(store, tenant, user, "same")
    delete_file_cascade(store, tenant, user, store.files[first])
    assert document in store.library_documents
    store.files[first]["status"] = "deleted"
    delete_file_cascade(store, tenant, user, store.files[second])
    assert document not in store.library_documents
    assert store.audit_log[-1]["action"] == "library_document.deleted"
    # A file with no hash has no reading to remove.
    plain = _file(store, tenant, user, "")
    delete_file_cascade(store, tenant, user, store.files[plain])


def test_a_reading_nobody_owns_is_still_removed_with_its_last_file() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    file_id = _file(store, tenant, user, "orphan")
    document = _library(store, tenant, uuid.uuid4(), "orphan")
    delete_file_cascade(store, tenant, user, store.files[file_id])
    assert document not in store.library_documents


def test_only_the_owner_deletes_a_library_document() -> None:
    store = _Store()
    tenant, owner, other = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    document = _library(store, tenant, owner, "one")
    with pytest.raises(NotFoundError):
        delete_library(store, Actor(tenant, other, frozenset({"chat:use"})), document)
    delete_library(store, Actor(tenant, owner, frozenset({"chat:use"})), document)
    assert store.library_documents == {}


def test_the_retention_sweep_removes_expired_files_and_their_bytes() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    expired = _file(store, tenant, user, "old", retention_until=now - timedelta(days=1))
    kept = _file(store, tenant, user, "new", retention_until=now + timedelta(days=1))
    forever = _file(store, tenant, user, "forever")
    ownerless = _file(store, tenant, None, "ownerless", retention_until=now - timedelta(days=1))
    already = _file(
        store, tenant, user, "already", status="deleted", retention_until=now - timedelta(days=1)
    )
    store.blobs[expired] = b"bytes"
    document = _library(store, tenant, user, "old")
    assert sweep_expired(store, now=now) == 1
    assert store.files[expired]["status"] == "deleted"
    assert expired not in store.blobs
    assert document not in store.library_documents
    for file_id in (kept, forever, ownerless):
        assert store.files[file_id]["status"] == "ready"
    assert store.files[already].get("deleted_at") is None


def test_reprocessing_reads_the_stored_original_again() -> None:
    store = demo_store()
    tenant, owner = uuid.uuid4(), uuid.uuid4()
    actor = Actor(tenant, owner, frozenset({"chat:use"}))
    library = DocumentLibrary(store)
    saved = library.ingest(
        actor, data=b"# Hours\n\nThe desk opens at eight.\n", filename="hours.md"
    )
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    row["passages"] = []
    row["status"] = "failed"
    again = reprocess(store, actor, document_id)
    assert again["status"] == "ready"
    assert "The desk opens at eight." in str(store.library_documents[document_id]["passages"])
    assert store.library_documents[document_id]["error_code"] is None
    with pytest.raises(NotFoundError):
        reprocess(store, Actor(tenant, uuid.uuid4(), frozenset({"chat:use"})), document_id)
    row["object_key"] = ""
    with pytest.raises(NotFoundError):
        reprocess(store, actor, document_id)


def test_the_uploads_collection_is_made_once_and_never_takes_a_name_in_use() -> None:
    store = demo_store()
    tenant = uuid.uuid4()
    actor = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    assert find_uploads(store, tenant) is None
    made = ensure_uploads(store, actor)
    assert made is not None
    assert is_system(made)
    assert made["slug"] == SLUG
    assert ensure_uploads(store, actor) is made
    assert find_uploads(store, uuid.uuid4()) is None

    taken = uuid.uuid4()
    theirs = uuid.uuid4()
    store.knowledge_collections[theirs] = {"id": theirs, "tenant_id": taken, "slug": "Uploads"}
    # Someone already made a collection with this name. It is theirs, so none is made.
    assert ensure_uploads(store, Actor(taken, uuid.uuid4(), frozenset({"chat:use"}))) is None


def test_a_section_without_a_model_is_an_error() -> None:
    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    file_id = _file(store, tenant, user, "one")
    _library(store, tenant, user, "one")
    run = _section_run(store, tenant, user, _conversation(store, tenant, [file_id]))
    job = begin_map(store, run, {"instruction": "Read it.", "fileIds": [str(file_id)]})
    sections = job["sections"]
    assert isinstance(sections, list)
    with pytest.raises(ArError):
        run_section(store, run, sections[0])


def _indexed(store: object, tenant: uuid.UUID, user: uuid.UUID, file_id: object) -> uuid.UUID:
    """A knowledge document built from ``file_id``, in a collection made the product's way."""
    from ar_domain.knowledge.book import KnowledgeBook

    manager = Actor(tenant, user, frozenset({"knowledge:manage", "knowledge:read"}))
    view = KnowledgeBook(store).create_collection(
        manager, {"slug": f"c-{uuid.uuid4().hex[:8]}", "name": "Shelf", "visibility": "tenant"}
    )
    knowledge = uuid.uuid4()
    store.knowledge_documents[knowledge] = {  # type: ignore[attr-defined]
        "id": knowledge,
        "tenant_id": tenant,
        "collection_id": uuid.UUID(str(view["id"])),
        "raw_file_id": file_id,
        "status": "indexed",
        "version_hash": "",
    }
    return knowledge


def test_deleting_a_file_removes_the_knowledge_document_built_from_it() -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": user,
        "sha256": "",
        "status": "deleted",
    }
    knowledge = _indexed(store, tenant, user, file_id)
    untouched = _indexed(store, tenant, user, uuid.uuid4())
    delete_file_cascade(store, tenant, user, store.files[file_id])
    assert store.knowledge_documents[knowledge]["status"] == "deleted"
    assert store.knowledge_documents[untouched]["status"] == "indexed"


def test_deleting_a_library_document_removes_what_was_indexed_from_its_bytes() -> None:
    store = demo_store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = Actor(tenant, user, frozenset({"chat:use"}))
    saved = DocumentLibrary(store).ingest(
        actor, data=b"# Hours\n\nThe desk opens at eight.\n", filename="hours.md"
    )
    document_id = uuid.UUID(str(saved["id"]))
    digest = str(store.library_documents[document_id]["content_hash"])
    file_id = uuid.uuid4()
    store.files[file_id] = {"id": file_id, "tenant_id": tenant, "sha256": digest, "status": "ready"}
    from_file = _indexed(store, tenant, user, file_id)
    by_hash = _indexed(store, tenant, user, None)
    store.knowledge_documents[by_hash]["version_hash"] = digest
    elsewhere = _indexed(store, uuid.uuid4(), user, file_id)
    delete_library(store, actor, document_id)
    assert store.knowledge_documents[from_file]["status"] == "deleted"
    assert store.knowledge_documents[by_hash]["status"] == "deleted"
    assert store.knowledge_documents[elsewhere]["status"] == "indexed"


def test_sections_under_different_headings_pair_by_meaning_or_by_shared_words() -> None:
    from ar_domain.documents.align import align

    left = [
        {
            "anchor": "p1-s0",
            "heading": "Settlement",
            "text": "Invoices are settled within thirty days of receipt.",
            "embedding": [1.0, 0.0],
        },
        {"anchor": "p1-s1", "heading": "Parking", "text": "Visitors park behind the building."},
        {"anchor": "p1-s2", "heading": "Retired", "text": "Fax numbers are listed here."},
    ]
    right = [
        {
            "anchor": "p2-s0",
            "heading": "Paying suppliers",
            "text": "Suppliers are paid in a month.",
            "embedding": [1.0, 0.0],
        },
        {
            "anchor": "p2-s1",
            "heading": "Cars",
            "text": "Visitors park behind the building, in the marked bays.",
            "embedding": [0.0, "not a number"],
        },
    ]
    rows = align(left, right)
    by_left = {row.get("leftAnchor"): row for row in rows}
    assert by_left["p1-s0"]["status"] == "paired"
    assert by_left["p1-s0"]["rightAnchor"] == "p2-s0"
    assert by_left["p1-s1"]["rightAnchor"] == "p2-s1"
    assert by_left["p1-s2"]["status"] == "removed"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (b"stream: Win.Test.EICAR_HDB-1 FOUND\0", "infected"),
        (b"INSTREAM size limit exceeded. ERROR\0", "error"),
        (b"", "error"),
    ],
)
def test_the_scanner_reply_decides_and_anything_unclear_is_an_error(
    reply: bytes, expected: str
) -> None:
    import socket
    import threading

    from ar_domain.files.clamav import instream

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        conn, _addr = server.accept()
        conn.settimeout(2)
        try:
            held = b""
            while not held.endswith(b"hello\x00\x00\x00\x00"):
                piece = conn.recv(65536)
                if not piece:
                    break
                held += piece
            conn.sendall(reply)
        finally:
            conn.close()
            server.close()

    threading.Thread(target=serve, daemon=True).start()
    assert instream(b"hello", f"127.0.0.1:{port}", timeout_s=2) == expected


def test_a_scanner_that_cannot_be_reached_is_an_error_not_a_clean_file(tmp_path: object) -> None:
    from ar_domain.files.clamav import instream

    assert instream(b"hello", "  ", timeout_s=1) == "error"
    assert instream(b"hello", "no-port", timeout_s=1) == "error"
    assert instream(b"hello", "127.0.0.1:1", timeout_s=1) == "error"
    assert instream(b"hello", f"{tmp_path}/no-such.sock", timeout_s=1) == "error"


def test_an_upload_is_parsed_by_its_kind_and_an_unknown_kind_is_refused() -> None:
    from ar_domain.knowledge.parse import ParseError, parse_bytes

    limit = 10_000
    plain = parse_bytes(b"plain words", mime_type="text/plain", name="a.txt", max_bytes=limit)
    assert plain.endswith("plain words")
    page = b"<html><style>p{}</style><h2>Hours</h2><p>Opens at eight.</p><nav>skip</nav></html>"
    html = parse_bytes(page, mime_type="text/html", name="a.html", max_bytes=limit)
    assert "## Hours" in html
    assert "Opens at eight." in html
    assert "skip" not in html
    table = parse_bytes(b"id,amount\n1,10\n", mime_type="text/csv", name="a.csv", max_bytes=limit)
    assert "id" in table
    assert "amount" in table
    with pytest.raises(ParseError) as large:
        parse_bytes(b"x" * 11, mime_type="text/plain", name="a.txt", max_bytes=10)
    assert large.value.code == "too_large"
    with pytest.raises(ParseError) as broken:
        parse_bytes(b"not a pdf", mime_type="application/pdf", name="a.pdf", max_bytes=limit)
    assert broken.value.code in {"unsupported_format", "too_large"}


def test_a_section_is_summarised_by_the_tenant_model_when_it_has_one() -> None:
    from ar_domain.chat.service import demo_id
    from ar_testing.demo import connect_chat

    store = demo_store()
    tenant, user = demo_id("tenant"), demo_id("admin")
    connect_chat(store, tenant)
    file_id = uuid.uuid4()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": tenant,
        "owner_user_id": user,
        "sha256": "one",
        "status": "ready",
        "name": "one.md",
    }
    document_id = uuid.uuid4()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "owner_user_id": user,
        "content_hash": "one",
        "status": "ready",
        "passages": [
            {"anchor": "p1-s0", "page": 1, "heading": "Hours", "text": "The desk opens at eight."},
            {"anchor": "p1-s1", "page": 1, "heading": "Blank", "text": "   "},
        ],
    }
    conversation = uuid.uuid4()
    message = uuid.uuid4()
    store.messages[message] = {
        "id": message,
        "tenant_id": tenant,
        "conversation_id": conversation,
        "role": "user",
        "created_at": "2026-11-20T00:00:00Z",
        "content": [{"type": "file", "file_id": str(file_id)}],
    }
    run: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "user_id": user,
        "conversation_id": conversation,
    }
    store.runs[run["id"]] = run  # type: ignore[index]
    store.conversations[conversation] = {}

    def answered(*args: object) -> str:
        return "Opens at eight." if str(args[-1]).strip() else ""

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("ar_domain.documents.sections._read_model", answered)
    try:
        job = begin_map(store, run, {"instruction": "Read it.", "fileIds": [str(file_id)]})
        pending = job["sections"]
        assert isinstance(pending, list)
        read = run_section(store, run, pending[0])
        assert read["output"] == "Opens at eight."
        assert read["quote"] == "The desk opens at eight."
        blank = run_section(store, run, pending[1])
        assert blank["output"] == ""
    finally:
        monkeypatch.undo()


def test_files_an_agent_always_reads_are_listed_only_when_they_are_the_callers() -> None:
    from ar_domain.memory.session import _agent_lines

    store = _Store()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    mine = _file(store, tenant, user, "one", name="one.md")
    _library(store, tenant, user, "one")
    known = _file(store, tenant, user, "known", name="known.md")
    theirs = _file(store, tenant, uuid.uuid4(), "theirs", name="theirs.md")
    elsewhere = _file(store, uuid.uuid4(), user, "elsewhere", name="elsewhere.md")
    run: dict[str, object] = {"id": uuid.uuid4(), "tenant_id": tenant, "user_id": user}
    definition: dict[str, object] = {
        "knowledge": {"fileIds": [str(mine), str(known), str(theirs), str(elsewhere), "not-an-id"]}
    }
    lines = _agent_lines(store, run, definition, {known})
    assert f"[file: one.md id={mine}]" in lines
    assert "The desk opens at eight." in lines
    assert "theirs.md" in lines
    for name in ("known.md", "elsewhere.md"):
        assert name not in lines
    assert _agent_lines(store, run, {"knowledge": {}}, set()) == ""
    assert _agent_lines(store, run, {}, set()) == ""


def test_a_tool_is_bound_by_its_server_and_by_name_or_a_star() -> None:
    from ar_domain.exposure.runs import bound_tool, find_tool_version

    definition: dict[str, object] = {
        "tools": [
            "not a binding",
            {"server": "general", "include": ["query_table"]},
            {"server": "documents"},
        ]
    }
    assert bound_tool(definition, "general.query_table") is True
    assert bound_tool(definition, "general.export_table") is False
    assert bound_tool(definition, "documents.read") is True
    assert bound_tool(definition, "browser.open") is False
    assert bound_tool({}, "general.query_table") is False
    store = _Store()
    store.tool_versions = {  # type: ignore[attr-defined]
        1: "not a version",
        2: {"qualified_name": "general.query_table", "version": 3},
    }
    found = find_tool_version(store, "general.query_table")
    assert found is not None
    assert found["version"] == 3
    assert find_tool_version(store, "general.nothing") is None

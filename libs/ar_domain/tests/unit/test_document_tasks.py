"""Document tasks: strategy, alignment, owner ACL, sections and the scanner."""

from __future__ import annotations

import socket
import threading
import uuid

import pytest

from ar_common.errors import ArError, NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.documents.align import align
from ar_domain.documents.library import DocumentLibrary
from ar_domain.documents.sections import run_section
from ar_domain.documents.strategy import NamedText, documents_fit, usable_tokens
from ar_domain.documents.templates import apply_template, resolve_template
from ar_domain.files.logic import EICAR, scan_bytes


def test_the_window_is_measured_and_not_assumed() -> None:
    short = NamedText("f", "d", tokens=100, characters=400, headings=2)
    long = NamedText("f", "d", tokens=50_000, characters=200_000, headings=2)
    assert documents_fit([short], 32_768)[0] is True
    assert documents_fit([long], 32_768)[0] is False
    assert documents_fit([long], 262_144)[0] is True
    assert usable_tokens(None) is None
    assert usable_tokens(32_768) != usable_tokens(262_144)


def test_a_template_comes_from_the_agent_or_a_pack(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    definition = {
        "task_templates": [
            {
                "id": "outline",
                "prompt": "Outline each document.",
                "items": ["hours"],
                "output_schema": {"type": "object"},
            }
        ]
    }
    found = resolve_template(definition, "outline", packs_dir=str(root))
    text, items, schema = apply_template(
        found, instruction="Please.", items=[], response_format=None
    )
    assert text.startswith("Outline each document.")
    assert items == [{"id": "", "text": "hours"}]
    assert schema == {"type": "object"}
    folder = root / "sample" / "task-templates"
    folder.mkdir(parents=True)
    (folder / "outline.json").write_text(
        '{"id":"sketch","prompt":"List the headings.","items":[]}', encoding="utf-8"
    )
    (folder / "broken.json").write_text("not-json", encoding="utf-8")
    packed = resolve_template({}, "sketch", packs_dir=str(root))
    assert packed.prompt == "List the headings."
    shipped = resolve_template(None, "outline", packs_dir="packs/examples")
    assert shipped.prompt.startswith("Produce an outline")
    with pytest.raises(ArError):
        resolve_template({}, "missing", packs_dir=str(root))


def test_alignment_prefers_unpaired_to_a_weak_pair() -> None:
    left = [
        {"anchor": "p1-s0", "page": 1, "heading": "1. Payment", "text": "Pay within thirty days."}
    ]
    right = [
        {"anchor": "p2-s0", "page": 2, "heading": "Payment", "text": "Pay within ten days."},
        {
            "anchor": "p3-s0",
            "page": 3,
            "heading": "Garden",
            "text": "The garden is maintained weekly.",
        },
    ]
    rows = align(left, right)
    paired = [row for row in rows if row["status"] == "paired"]
    assert len(paired) == 1
    assert paired[0]["leftQuote"] == "Pay within thirty days."
    assert any(row["status"] == "added" and row["heading"] == "Garden" for row in rows)


def test_library_list_is_owner_only_inside_one_tenant() -> None:
    tenant = uuid.uuid4()
    owner = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    other = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    library = DocumentLibrary(_store())
    saved = library.ingest(owner, data=b"# Note\n\nThe desk opens at eight.", filename="note.md")
    assert library.list_items(owner)["documents"]
    assert library.list_items(other)["documents"] == []
    with pytest.raises(NotFoundError):
        library.get(other, uuid.UUID(str(saved["id"])))


def test_an_ownerless_row_is_hidden_and_a_collection_share_is_not() -> None:
    tenant = uuid.uuid4()
    owner = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    reader = Actor(tenant, uuid.uuid4(), frozenset({"chat:use"}))
    document_id = uuid.uuid4()
    file_id = uuid.uuid4()
    collection_id = uuid.uuid4()
    knowledge_id = uuid.uuid4()
    store = _store()
    store.files = {  # type: ignore[attr-defined]
        file_id: {
            "id": file_id,
            "tenant_id": tenant,
            "sha256": "digest",
            "deleted_at": None,
        },
        uuid.uuid4(): {"id": uuid.uuid4(), "tenant_id": tenant, "sha256": "other"},
    }
    store.library_documents = {  # type: ignore[attr-defined]
        document_id: {
            "id": document_id,
            "tenant_id": tenant,
            "owner_user_id": None,
            "content_hash": "digest",
            "status": "ready",
            "title": "Note",
            "filename": "note.md",
        }
    }
    library = DocumentLibrary(store)
    with pytest.raises(NotFoundError):
        library.get(owner, document_id)
    with pytest.raises(NotFoundError):
        library.get(reader, file_id)
    store.library_documents[document_id]["owner_user_id"] = owner.user_id
    assert library.get(owner, document_id)["id"] == str(document_id)
    with pytest.raises(NotFoundError):
        library.get(reader, document_id)
    store.knowledge_collections = {  # type: ignore[attr-defined]
        collection_id: {"id": collection_id, "tenant_id": tenant}
    }
    store.knowledge_documents = {  # type: ignore[attr-defined]
        knowledge_id: {
            "id": knowledge_id,
            "tenant_id": tenant,
            "collection_id": collection_id,
            "raw_file_id": file_id,
            "status": "indexed",
            "classification": "internal",
            "acl_principals": [f"user:{reader.user_id}"],
        }
    }
    assert library.get(reader, document_id)["id"] == str(document_id)


def test_a_section_retry_does_not_call_the_model_again() -> None:
    calls = {"n": 0}

    class Store:
        def __init__(self) -> None:
            self.runs: dict[object, dict[str, object]] = {}
            self.job_progress: dict[object, dict[str, object]] = {}
            self.audit_log: list[dict[str, object]] = []

    store = Store()
    run: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "conversation_id": uuid.uuid4(),
        "checkpoint": {
            "document_map": {
                "instruction": "Say when the desk opens.",
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
                "delivered": False,
            }
        },
    }
    store.runs[run["id"]] = run

    def model(
        store: object,
        run: dict[str, object],
        job: dict[str, object],
        section: dict[str, object],
        text: str,
    ) -> str:
        del store, run, job, section, text
        calls["n"] += 1
        return "Opens at eight."

    from ar_domain.documents import sections as mod

    original = mod._read_model
    mod._read_model = model  # type: ignore[assignment]
    try:
        section = {"fileId": "file-1", "anchor": "p1-s0"}
        first = run_section(store, run, section)
        second = run_section(store, run, section)
    finally:
        mod._read_model = original  # type: ignore[assignment]
    assert first["quote"] == "The desk opens at eight."
    assert second == first
    assert calls["n"] == 1


def test_clamav_fail_closed_and_a_live_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def settings() -> object:
        return type("S", (), {"clamav_address": "", "clamav_timeout_s": 2})()

    monkeypatch.setattr("ar_common.settings.get_settings", settings)
    assert scan_bytes(b"hello", scanner="clamav") == "error"
    assert scan_bytes(EICAR, scanner="clamav") == "infected"
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def serve() -> None:
        conn, _addr = server.accept()
        conn.settimeout(2)
        try:
            held = b""
            # Answer only once the whole stream is in: the command, then chunks that each
            # start with their length, ended by a chunk of length zero. Four zero bytes
            # also appear where the command's terminator meets the first length, so
            # looking for them anywhere answers, and closes, while the client still sends.
            while not _stream_ended(held):
                try:
                    piece = conn.recv(65536)
                except TimeoutError:
                    break
                if not piece:
                    break
                held += piece
            conn.sendall(b"stream: OK\0")
        finally:
            conn.close()
            server.close()

    threading.Thread(target=serve, daemon=True).start()
    assert scan_bytes(b"%PDF hello", scanner="clamav", address=f"127.0.0.1:{port}") == "clean"


def _stream_ended(held: bytes) -> bool:
    """Whether a clamd INSTREAM request has arrived whole."""
    command = b"zINSTREAM\0"
    if not held.startswith(command):
        return False
    at = len(command)
    while at + 4 <= len(held):
        size = int.from_bytes(held[at : at + 4], "big")
        if size == 0:
            return True
        at += 4 + size
    return False


def _store() -> object:
    class Store:
        def __init__(self) -> None:
            self.scanner = "none"
            self.audit_log: list[dict[str, object]] = []

    return Store()

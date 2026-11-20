"""Who reads an upload: the ingest worker when one is connected, whatever the size.

Three faults from the document certification handover of 20 November 2026 are held
here. A file over ``AR_INGEST_INLINE_MAX_BYTES`` went to the API instead of the worker.
A layout parser that failed left no trace. The task templates every install has were
not in the image.
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from pathlib import Path

import pytest

from ar_common.settings import get_settings
from ar_domain.documents import layout
from ar_domain.documents.create.render import render
from ar_domain.documents.create.spec import parse
from ar_domain.documents.templates import resolve_template
from ar_domain.knowledge import pipeline
from ar_domain.knowledge.pipeline import ingest_or_enqueue, stored_bytes
from ar_ingest.activities import bind_store, ingest_document_activity
from ar_testing.demo import demo_store
from ar_testing.sleeping import in_this_thread

_ROOT = Path(__file__).resolve().parents[4]


class _Handle:
    def __init__(self, hang: bool) -> None:
        self.hang = hang

    async def result(self) -> str:
        if self.hang:
            await asyncio.sleep(600)
        return "indexed"


class _Client:
    """Stands where the workflow engine's client is and keeps what it was asked to start."""

    def __init__(self, *, hang: bool = False) -> None:
        self.hang = hang
        self.started: list[dict[str, object]] = []

    async def start_workflow(self, _name: str, payload: dict[str, object], **_: object) -> _Handle:
        self.started.append(payload)
        return _Handle(self.hang)


def _upload(store: object, *, size: int) -> tuple[uuid.UUID, uuid.UUID, bytes]:
    """A stored file and the collection document made from it."""
    file_id, document_id = uuid.uuid4(), uuid.uuid4()
    raw = (b"The visitor desk opens at 08:30. " * (size // 33 + 1))[:size]
    store.files[file_id] = {"id": file_id, "status": "ready", "name": "a.md"}  # type: ignore[attr-defined]
    store.blobs[file_id] = raw  # type: ignore[attr-defined]
    store.knowledge_documents[document_id] = {  # type: ignore[attr-defined]
        "id": document_id,
        "status": "pending",
        "raw_file_id": file_id,
    }
    return file_id, document_id, raw


@pytest.fixture
def quiet_store(monkeypatch: pytest.MonkeyPatch) -> object:
    """A store whose saves and reloads go nowhere, and whose own parse is counted."""
    store = demo_store()

    async def _nothing(*_args: object) -> None:
        return None

    parsed: list[uuid.UUID] = []

    async def _parse_here(_store: object, document_id: uuid.UUID, _raw: bytes) -> str:
        parsed.append(document_id)
        return "indexed"

    monkeypatch.setattr("ar_domain.durable.flush.flush_store", _nothing)
    monkeypatch.setattr("ar_domain.durable.hydrate.reload_document", _nothing)
    monkeypatch.setattr(pipeline, "ingest_document_async", _parse_here)
    store.parsed_here = parsed  # type: ignore[attr-defined]
    return store


@pytest.mark.asyncio
async def test_a_large_upload_goes_to_the_worker_by_reference(quiet_store: object) -> None:
    store = quiet_store
    over = int(get_settings().ingest_inline_max_bytes) + 1
    _file, document_id, raw = _upload(store, size=over)
    client = _Client()
    store.temporal_client = client  # type: ignore[attr-defined]

    await ingest_or_enqueue(store, document_id, raw)

    # The worker was asked, the bytes did not travel with the request, and the API
    # did not read the file itself.
    assert client.started == [{"document_id": str(document_id)}]
    assert store.parsed_here == []  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_small_upload_travels_with_the_request(quiet_store: object) -> None:
    store = quiet_store
    _file, document_id, raw = _upload(store, size=64)
    client = _Client()
    store.temporal_client = client  # type: ignore[attr-defined]

    await ingest_or_enqueue(store, document_id, raw)

    assert base64.b64decode(str(client.started[0]["raw_b64"])) == raw
    assert store.parsed_here == []  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_large_file_in_no_file_store_is_read_here(quiet_store: object) -> None:
    store = quiet_store
    over = int(get_settings().ingest_inline_max_bytes) + 1
    document_id = uuid.uuid4()
    store.knowledge_documents[document_id] = {"id": document_id, "status": "pending"}  # type: ignore[attr-defined]
    client = _Client()
    store.temporal_client = client  # type: ignore[attr-defined]

    assert await ingest_or_enqueue(store, document_id, b"x" * over) == "indexed"

    # Nothing the worker could read it from, so the only reader left is this process.
    assert client.started == []
    assert store.parsed_here == [document_id]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_slow_worker_is_not_raced_on_a_large_file(
    quiet_store: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = quiet_store
    over = int(get_settings().ingest_inline_max_bytes) + 1
    _file, large_id, large = _upload(store, size=over)
    _file, small_id, small = _upload(store, size=64)
    store.temporal_client = _Client(hang=True)  # type: ignore[attr-defined]
    waits: list[float] = []

    async def _gave_up(awaitable: object, **limits: float) -> None:
        waits.append(limits["timeout"])
        awaitable.close()  # type: ignore[attr-defined]
        raise TimeoutError

    monkeypatch.setattr(asyncio, "wait_for", in_this_thread(_gave_up, asyncio.wait_for))

    # The large file stays with the worker: the answer is the document as it stands.
    assert await ingest_or_enqueue(store, large_id, large) == "pending"
    assert store.parsed_here == []  # type: ignore[attr-defined]
    # A small file is still read here when the worker does not answer in time.
    assert await ingest_or_enqueue(store, small_id, small) == "indexed"
    assert store.parsed_here == [small_id]  # type: ignore[attr-defined]
    assert waits[0] > waits[1]


def test_the_stored_file_is_what_the_worker_reads() -> None:
    store = demo_store()
    _file, document_id, raw = _upload(store, size=120)
    assert stored_bytes(store, document_id) == raw
    # A document made from typed text has no stored file.
    typed = uuid.uuid4()
    store.knowledge_documents[typed] = {"id": typed, "status": "pending"}
    assert stored_bytes(store, typed) == b""
    assert stored_bytes(store, uuid.uuid4()) == b""


def test_the_worker_reads_a_file_that_did_not_travel(monkeypatch: pytest.MonkeyPatch) -> None:
    store = demo_store()
    _file, document_id, raw = _upload(store, size=200)
    read: list[bytes] = []

    async def _keep(_store: object, _document_id: uuid.UUID, data: bytes) -> str:
        read.append(data)
        return "indexed"

    monkeypatch.setattr("ar_ingest.activities.ingest_document_async", _keep)
    bind_store(store)
    answer = asyncio.run(ingest_document_activity({"document_id": str(document_id)}))

    assert answer["status"] == "indexed"
    assert read == [raw]


def _docx() -> bytes:
    return render(
        parse(
            {
                "format": "docx",
                "title": "Policy",
                "sections": [
                    {"heading": "Access", "level": 1, "paragraphs": ["The door stays locked."]},
                ],
            }
        )
    )


def test_a_layout_parser_that_fails_is_named_on_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Broken:
        def convert(self, _path: str) -> object:
            raise RuntimeError("model files are missing")

    seen: list[tuple[str, dict[str, object]]] = []

    class _Log:
        def warning(self, event: str, **fields: object) -> None:
            seen.append((event, fields))

    monkeypatch.setattr(layout, "_converter", _Broken)
    monkeypatch.setattr(layout, "_log", _Log())
    monkeypatch.setattr(
        "importlib.util.find_spec", lambda name, *_a: object() if "docling" in name else None
    )

    extracted = layout.parse_layout(_docx(), filename="policy.docx")

    # The text is still read, and the document says who read it and why.
    assert any("door stays locked" in passage.text for passage in extracted.passages)
    assert extracted.metadata["parser"] == "fallback"
    assert extracted.metadata["parserNote"] == "layout_parser_failed:RuntimeError"
    # The log line carries the kind of error and of file. It carries no name and no text.
    assert seen == [
        (
            "layout_parser_failed",
            {"error": "RuntimeError", "kind": "docx", "bytes": len(_docx())},
        )
    ]


def test_a_missing_layout_parser_is_named_too(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda *_a: None)
    extracted = layout.parse_layout(_docx(), filename="policy.docx")
    assert extracted.metadata["parser"] == "fallback"
    assert extracted.metadata["parserNote"] == "layout_parser_not_installed"
    # A kind the layout parser is not asked to read carries no such note.
    plain = layout.parse_layout(b"# Desk\n\nOpens at eight.\n", filename="desk.md")
    assert "parserNote" not in plain.metadata


def test_the_image_holds_every_template_the_product_ships() -> None:
    """The image is built from the repository, so what it copies is checked against it."""
    image = (_ROOT / "images" / "python-service.Dockerfile").read_text()
    folder = "packs/examples/task-templates"
    assert f"COPY {folder} {folder}" in image
    # Read the way the product reads them, from the folder the image copies.
    shipped = sorted(path.stem for path in (_ROOT / folder).glob("*.json"))
    assert shipped
    for template_id in shipped:
        found = resolve_template(None, template_id, packs_dir=str(_ROOT / "packs"))
        assert found.id == template_id

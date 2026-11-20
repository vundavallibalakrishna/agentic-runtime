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
from ar_domain.documents.strategy import NamedText, choose, usable_tokens
from ar_domain.files.logic import EICAR, scan_bytes
from ar_domain.runs.request import ask


def test_strategy_follows_the_registered_window() -> None:
    short = NamedText("f", "d", tokens=100, characters=400, headings=2)
    long = NamedText("f", "d", tokens=50_000, characters=200_000, headings=2)
    assert choose("question", "auto", [short], 32_768).strategy == "full"
    assert choose("question", "auto", [long], 32_768).strategy == "retrieve"
    assert choose("summarise", "auto", [long], 262_144).strategy == "full"
    assert choose("summarise", "auto", [long], None).strategy == "map_reduce"
    assert usable_tokens(None) is None
    assert usable_tokens(32_768) != usable_tokens(262_144)
    with pytest.raises(ArError) as refused:
        choose("question", "full", [long], 32_768)
    assert refused.value.code.value == "invalid_state"


def test_alignment_prefers_unpaired_to_a_weak_pair() -> None:
    left = [
        {"anchor": "p1-s0", "page": 1, "heading": "1. Payment", "text": "Pay within thirty days."}
    ]  # noqa: E501
    right = [
        {"anchor": "p2-s0", "page": 2, "heading": "Payment", "text": "Pay within ten days."},
        {
            "anchor": "p3-s0",
            "page": 3,
            "heading": "Garden",
            "text": "The garden is maintained weekly.",
        },  # noqa: E501
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
    assert library.list_items(owner)
    assert library.list_items(other) == []
    with pytest.raises(NotFoundError):
        library.get(other, uuid.UUID(str(saved["id"])))


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
    }
    ask(run, "strategy", "map_reduce")
    store.runs[run["id"]] = run

    def model(store: object, run: dict[str, object], section: dict[str, object], text: str) -> str:
        del store, run, section
        calls["n"] += 1
        return "Opens at eight."

    from ar_domain.documents import sections as mod

    original = mod._summarise
    mod._summarise = model  # type: ignore[assignment]
    try:
        section = {"fileId": "file-1", "anchor": "p1-s0"}
        first = run_section(store, run, section)
        second = run_section(store, run, section)
    finally:
        mod._summarise = original  # type: ignore[assignment]
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
            conn.sendall(b"stream: OK\0")
        finally:
            conn.close()
            server.close()

    threading.Thread(target=serve, daemon=True).start()
    assert scan_bytes(b"%PDF hello", scanner="clamav", address=f"127.0.0.1:{port}") == "clean"


def _store() -> object:
    class Store:
        def __init__(self) -> None:
            self.scanner = "none"
            self.audit_log: list[dict[str, object]] = []

    return Store()

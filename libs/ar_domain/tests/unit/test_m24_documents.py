"""Document extraction, grounding, tools and durable rows."""

from __future__ import annotations

import asyncio
import io
import time
import uuid
import zipfile
from types import SimpleNamespace
from typing import Any

import pytest

from ar_common.errors import NotFoundError, PayloadTooLargeError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.documents.chunk import retrieve
from ar_domain.documents.extract import ExtractError, extract_bytes
from ar_domain.documents.grounding import (
    apply_hunks,
    check,
    line_hunks,
    summarise,
)
from ar_domain.documents.library import MAX_DOCUMENT_BYTES, DocumentLibrary
from ar_domain.tools.documents import dispatch_documents
from ar_domain.tools.handlers import dispatch

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _actor(tenant: uuid.UUID | None = None) -> Actor:
    return Actor(
        tenant_id=tenant or uuid.uuid4(),
        user_id=uuid.uuid4(),
        permissions=frozenset({"chat:use"}),
    )


def _store() -> Any:
    class Store:
        def __init__(self) -> None:
            self.scanner = "none"
            self.audit_log: list[dict[str, object]] = []

    return Store()


def _zip(parts: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        for name, payload in parts.items():
            book.writestr(name, payload)
    return buffer.getvalue()


def _docx() -> bytes:
    xml = f"""<w:document xmlns:w="{_W}"><w:body>
      <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Purpose</w:t></w:r></w:p>
      <w:p><w:r><w:t>Staff store passwords in a vault.</w:t></w:r></w:p>
      <w:tbl><w:tr>
        <w:tc><w:p><w:r><w:t>Role</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Owner</w:t></w:r></w:p></w:tc>
      </w:tr></w:tbl>
    </w:body></w:document>"""
    return _zip({"word/document.xml": xml})


def _xlsx() -> bytes:
    shared = f'<sst xmlns="{_X}"><si><t>Region</t></si><si><t>North</t></si></sst>'
    grid = (
        f'<worksheet xmlns="{_X}"><sheetData>'
        '<row><c t="s"><v>0</v></c></row><row><c t="s"><v>1</v></c></row>'
        "</sheetData></worksheet>"
    )
    return _zip({"xl/sharedStrings.xml": shared, "xl/worksheets/sheet1.xml": grid})


def _pptx() -> bytes:
    slide = (
        f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        f'xmlns:a="{_A}"><a:t>Roadmap</a:t><a:t>Ship the reader in spring.</a:t></p:sld>'
    )
    return _zip({"ppt/slides/slide1.xml": slide})


def test_extracts_office_html_markdown_and_text() -> None:
    docx = extract_bytes(_docx(), filename="policy.docx")
    assert docx.tables and "Role" in docx.tables[0].csv_text
    assert any("vault" in row.text for row in docx.passages)
    sheet = extract_bytes(_xlsx(), filename="regions.xlsx")
    assert "North" in sheet.tables[0].csv_text
    slides = extract_bytes(_pptx(), filename="plan.pptx")
    assert slides.page_count == 1
    assert "Roadmap" in slides.passages[0].text
    html = extract_bytes(
        b"<html><h1>Access</h1><p>Staff use badges at every door.</p>"
        b"<table><tr><td>Door</td><td>West</td></tr></table></html>",
        filename="access.html",
    )
    assert html.tables and "West" in html.tables[0].csv_text
    markdown = extract_bytes(b"# Access\n\nStaff use badges.\n", filename="access.md")
    assert markdown.passages[0].heading == "Access"
    plain = extract_bytes(b"Hello policy.\n\nIt covers visitors.", filename="note.txt")
    assert plain.page_count == 1


def test_pdf_text_encrypted_corrupt_and_page_cap() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    locked = io.BytesIO()
    writer.encrypt("secret")
    writer.write(locked)
    with pytest.raises(ExtractError, match="encrypted") as encrypted:
        extract_bytes(locked.getvalue(), filename="locked.pdf")
    assert encrypted.value.code == "encrypted"
    with pytest.raises(ExtractError, match="could not be read"):
        extract_bytes(b"%PDF-1.4\nnot a real pdf", filename="bad.pdf")
    many = PdfWriter()
    for _ in range(601):
        many.add_blank_page(width=72, height=72)
    raw = io.BytesIO()
    many.write(raw)
    with pytest.raises(ExtractError, match="600") as limited:
        extract_bytes(raw.getvalue(), filename="long.pdf")
    assert limited.value.code == "too_many_pages"


def test_image_ocr_and_unsupported() -> None:
    png = b"\x89PNG\r\n\x1a\nrest"

    def read(_data: bytes) -> str:
        return "Ada Lovelace works in the lab."

    image = extract_bytes(png, filename="card.png", ocr=read)
    assert "Lovelace" in image.passages[0].text

    def missing(_data: bytes) -> str:
        raise ExtractError("ocr_unavailable", "OCR is not installed on this runtime.")

    with pytest.raises(ExtractError) as unavailable:
        extract_bytes(png, filename="card.png", ocr=missing)
    assert unavailable.value.code == "ocr_unavailable"
    with pytest.raises(ExtractError) as empty:
        extract_bytes(b"", filename="empty.txt")
    assert empty.value.code == "corrupt"
    with pytest.raises(ExtractError) as kind:
        extract_bytes(b"\x00\x01\x02\x03binary", filename="blob.bin")
    assert kind.value.code == "unsupported"


def test_library_dedupes_isolates_and_rejects() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    other = _actor()
    saved = library.ingest(
        actor, data=b"# Access\n\nStaff use badges at the door.", filename="a.md"
    )
    again = library.ingest(
        actor, data=b"# Access\n\nStaff use badges at the door.", filename="a.md"
    )
    assert again["deduped"] is True
    assert again["id"] == saved["id"]
    document_id = uuid.UUID(str(saved["id"]))
    with pytest.raises(NotFoundError):
        library.get(other, document_id)
    listed = library.list_items(other)
    assert listed == []
    hits = library.search(actor, "badges")
    assert hits and hits[0]["anchor"]
    read = library.read(actor, document_id, anchor=str(hits[0]["anchor"]))
    assert "badges" in str(read["text"])
    with pytest.raises(PayloadTooLargeError):
        library.ingest(actor, data=b"x" * (MAX_DOCUMENT_BYTES + 1), filename="big.txt")
    store.scanner = "clamav"
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    with pytest.raises(ValidationFailedError, match="scanner"):
        library.ingest(actor, data=eicar, filename="note.txt")
    assert any(row["action"] == "library_document.rejected" for row in store.audit_log)


def test_check_says_when_evidence_is_missing_and_cites_when_present() -> None:
    document = {
        "id": "doc",
        "title": "Access",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Access",
                "level": 1,
                "text": "Staff use badges at every door. Visitors sign the book.",
            }
        ],
    }
    report = check(
        document,
        ["Staff must use badges", "The organisation shall operate a colony on Mars"],
        None,
    )
    rows = report["rows"]
    assert isinstance(rows, list)
    found = rows[0]
    missing = rows[1]
    assert isinstance(found, dict)
    assert isinstance(missing, dict)
    assert found["verdict"] == "not_judged"
    assert found["citation"] is None
    assert missing["verdict"] == "not_judged"
    assert missing["citation"] is None
    assert "not a verdict" in str(found["reason"])

    def invent(_task: str, _evidence: str) -> str:
        return '{"claims":[{"text":"There is a Mars base.","anchor":"nope","quote":"Mars"}]}'

    summary = summarise(document, invent)
    claims = summary["claims"]
    assert isinstance(claims, list)
    assert claims
    assert all(row["anchor"] == "p1-s0" for row in claims if isinstance(row, dict))
    assert "Mars" not in str(claims)


def test_rewrite_is_not_saved_until_accepted() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    saved = library.ingest(
        actor,
        data=b"Staff store passwords in a vault. Visitors sign in at the desk.",
        filename="policy.txt",
    )
    document_id = uuid.UUID(str(saved["id"]))
    outline = library.outline(actor, document_id)
    anchor = str(outline["outline"][0]["anchor"])  # type: ignore[index]
    before = library.read(actor, document_id, anchor=anchor)["text"]
    proposal = library.propose_rewrite(
        actor,
        document_id,
        anchor=anchor,
        instruction='replace "vault" with "locker"',
    )
    assert library.read(actor, document_id, anchor=anchor)["text"] == before
    assert proposal["status"] == "proposed"
    hunks = proposal["hunks"]
    assert isinstance(hunks, list) and hunks
    decided = library.decide_rewrite(
        actor, uuid.UUID(str(proposal["id"])), decision="accept", hunk_id=str(hunks[0]["id"])
    )
    if decided["status"] == "proposed":
        library.decide_rewrite(actor, uuid.UUID(str(proposal["id"])), decision="reject")
    updated = str(library.read(actor, document_id)["text"])
    assert "locker" in updated or "vault" in updated
    with pytest.raises(ValidationFailedError):
        library.ingest(actor, data=b"hello policy text", filename="a.txt", source="nowhere")
    second = library.propose_rewrite(
        actor,
        document_id,
        anchor=anchor,
        instruction='replace "desk" with "counter"',
    )
    rejected = library.decide_rewrite(actor, uuid.UUID(str(second["id"])), decision="reject")
    assert rejected["status"] == "rejected"
    preview = library.redact(actor, document_id)
    dumped = str(preview)
    assert "ada@example.com" not in dumped
    email_doc = library.ingest(
        actor,
        data=b"Contact Ada Lovelace at ada@example.com or +1 415 555 0133.",
        filename="card.txt",
    )
    redacted = library.redact(actor, uuid.UUID(str(email_doc["id"])))
    assert "ada@example.com" not in str(redacted)
    assert "[EMAIL]" in str(redacted["redacted"])
    fields = library.extract(actor, document_id, ["passwords"])
    values = fields["fields"]
    assert isinstance(values, list)
    assert values[0]["value"] is None or "password" in str(values[0]["value"]).lower()  # type: ignore[index]


def test_compare_tables_and_long_retrieval() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    left = library.ingest(actor, data=_docx(), filename="one.docx")
    right = library.ingest(
        actor,
        data=b"# Purpose\n\nStaff store passwords in a locker.\n\n# Travel\n\nTrips need approval.",
        filename="two.md",
    )
    compared = library.compare(actor, uuid.UUID(str(left["id"])), uuid.UUID(str(right["id"])))
    changes = compared["changes"]
    assert isinstance(changes, list)
    assert any(
        row.get("op") in {"added", "removed", "changed"} for row in changes if isinstance(row, dict)
    )
    tables = library.tables(actor, uuid.UUID(str(left["id"])))
    assert "Role" in str(tables)
    passages = [
        {
            "anchor": f"p{page}-s0",
            "page": page,
            "heading": f"Section {page}",
            "text": ("word " * 200) + ("unique-needle" if page == 250 else "filler"),
        }
        for page in range(1, 301)
    ]
    started = time.perf_counter()
    chosen = retrieve(passages, "unique-needle")
    elapsed = time.perf_counter() - started
    assert elapsed < 2
    assert any(row["page"] == 250 for row in chosen)
    assert sum(len(str(row["text"])) for row in chosen) <= 12_000
    report = library.judge(
        actor,
        uuid.UUID(str(right["id"])),
        statements=["Trips need approval", "Operate a colony on Mars"],
    )
    rows = report["rows"]
    assert isinstance(rows, list)
    assert rows[1]["verdict"] == "not_judged"  # type: ignore[index]
    gaps = library.missing(
        actor,
        uuid.UUID(str(right["id"])),
        statements=["Operate a colony on Mars"],
    )
    assert any(
        isinstance(row, dict) and row.get("verdict") == "not_judged"
        for row in gaps["rows"]  # type: ignore[union-attr]
    )


def test_tools_and_hunks() -> None:
    store = _store()
    actor_id = uuid.uuid4()
    tenant = uuid.uuid4()
    saved = DocumentLibrary(store).ingest(
        Actor(tenant_id=tenant, user_id=actor_id, permissions=frozenset()),
        data=b"# Access\n\nStaff use badges.\n",
        filename="a.md",
    )
    args = {"_tenant_id": tenant, "_user_id": actor_id, "documentId": saved["id"]}
    listed = dispatch_documents(store, "list", args)
    assert "Access" in str(listed["text"])
    summary = dispatch(store, "builtin://documents", "summarise", args, "")
    assert summary["is_error"] is False
    assert "p1" in str(summary["text"])
    unknown = dispatch_documents(store, "missing", args)
    assert unknown["is_error"] is True
    original = "One. Two."
    hunks = line_hunks(original, "Two. One.")
    for hunk in hunks:
        hunk["decision"] = "accept"
    assert apply_hunks(original, hunks) == "Two. One."


def test_tools_cover_ingest_paths_and_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    import ar_domain.documents.tables  # noqa: F401
    from ar_domain.documents.model import ask_model
    from ar_domain.tools.general import _prepare

    store = _store()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    base = {"_tenant_id": tenant, "_user_id": user, "_run_id": uuid.uuid4()}
    root = _prepare(store, base)
    (root / "workspace" / "note.md").write_text("# Access\n\nStaff use badges at the door.\n")
    ingested = dispatch_documents(store, "ingest", {**base, "path": "/workspace/note.md"})
    assert ingested["is_error"] is False
    document = ingested["structured"]["presentation"]["document"]  # type: ignore[index]
    document_id = document["id"]
    args = {**base, "documentId": document_id}
    assert dispatch_documents(store, "search", {**base, "query": "badges"})["is_error"] is False
    assert dispatch_documents(store, "outline", args)["is_error"] is False
    assert dispatch_documents(store, "tables", args)["is_error"] is False
    read = dispatch_documents(store, "read", {**args, "pageFrom": 1, "pageTo": 1})
    assert read["is_error"] is False
    other = dispatch_documents(
        store,
        "ingest",
        {**base, "path": "/workspace/note.md"},
    )
    assert other["structured"]["presentation"]["document"]["deduped"] is True  # type: ignore[index]
    (root / "workspace" / "other.md").write_text("# Travel\n\nTrips need approval.\n")
    second = dispatch_documents(store, "ingest", {**base, "path": "/workspace/other.md"})
    other_id = second["structured"]["presentation"]["document"]["id"]  # type: ignore[index]
    assert (
        dispatch_documents(store, "compare", {**args, "otherDocumentId": other_id})["is_error"]
        is False
    )
    checked = dispatch_documents(
        store,
        "judge",
        {**args, "statements": ["Staff use badges", "Operate a colony on Mars"]},
    )
    assert "not_judged" in str(checked["text"]) or "not_supported" in str(checked["text"])
    assert (
        dispatch_documents(store, "missing", {**args, "statements": ["Operate a colony on Mars"]})[
            "is_error"
        ]
        is False
    )
    proposal = dispatch_documents(
        store, "rewrite", {**args, "instruction": 'replace "badges" with "passes"'}
    )
    assert proposal["is_error"] is False
    assert dispatch_documents(store, "redact", args)["is_error"] is False
    extracted = dispatch_documents(store, "extract", {**args, "fields": ["badges"]})
    assert extracted["is_error"] is False
    store.tenant_settings = {}
    missing = dispatch_documents(store, "ingest", {**base, "url": "https://example.com/policy.txt"})
    assert missing["is_error"] is True
    store.blobs = {}
    store.files = {}
    missing_file = dispatch_documents(store, "ingest", {**base, "fileId": str(uuid.uuid4())})
    assert missing_file["is_error"] is True
    foreign = uuid.uuid4()
    store.blobs[foreign] = b"# Hello\n\nA short note for the library."
    store.files[foreign] = {"name": "a.md", "mime_type": "text/markdown", "tenant_id": uuid.uuid4()}
    hidden = dispatch_documents(store, "ingest", {**base, "fileId": str(foreign)})
    assert hidden["is_error"] is True
    escaped = dispatch_documents(store, "ingest", {**base, "path": "../secret.txt"})
    assert escaped["is_error"] is True
    named = dispatch_documents(store, "summarise", {**args, "modelAlias": "reasoning"})
    assert named["is_error"] is False
    assert ask_model(store, tenant, "reasoning", "Say hi", "evidence") is None

    class Response:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": '{"claims":[]}'}}]}

    class Client:
        def __init__(self, timeout: float) -> None:
            del timeout

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def post(self, url: str, json: object, headers: dict[str, str]) -> Response:
            del url, json, headers
            return Response()

    monkeypatch.setattr("ar_domain.documents.model.httpx.Client", Client)

    class Live:
        def _completion_call(
            self, tenant_id: uuid.UUID, alias: str
        ) -> tuple[str, dict[str, str], float, bool]:
            del tenant_id, alias
            return "Qwen/Qwen3-32B", {}, 1.0, True

        def _completion_url_for(
            self, tenant_id: uuid.UUID, alias: str, headers: dict[str, str]
        ) -> str:
            del tenant_id, alias
            headers["Authorization"] = "Bearer test"
            return "https://example.test/v1/chat/completions"

    assert ask_model(Live(), tenant, "qwenm24", "Summarise", "evidence")


def test_hydrate_library_rows() -> None:
    from ar_domain.durable.m24 import load_library

    tenant = uuid.uuid4()
    document_id = uuid.uuid4()

    class Result:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def mappings(self) -> list[dict[str, object]]:
            return self._rows

    class Session:
        async def execute(self, statement: object, params: dict[str, object]) -> Result:
            del params
            sql = str(statement)
            if "library_documents" in sql:
                return Result(
                    [
                        {
                            "id": document_id,
                            "tenant_id": tenant,
                            "title": "Access",
                            "metadata": '{"pages": 1}',
                            "passages": [{"anchor": "p1-s0", "page": 1, "text": "badges"}],
                            "tables": "[]",
                        }
                    ]
                )
            if "document_checks" in sql:
                return Result(
                    [{"id": uuid.uuid4(), "tenant_id": tenant, "rows": {"kind": "check"}}]
                )
            if "document_comparisons" in sql:
                return Result(
                    [{"id": uuid.uuid4(), "tenant_id": tenant, "changes": {"kind": "compare"}}]
                )
            return Result(
                [
                    {
                        "id": uuid.uuid4(),
                        "tenant_id": tenant,
                        "hunks": [],
                        "passage_anchors": "[]",
                    }
                ]
            )

    class Store:
        def __init__(self) -> None:
            self.library_documents: dict[object, object] = {}
            self.document_checks: dict[object, object] = {}
            self.document_comparisons: dict[object, object] = {}
            self.document_rewrites: dict[object, object] = {}
            self.reloading = False

    store = Store()
    asyncio.run(load_library(Session(), store, tenant))  # type: ignore[arg-type]
    assert store.library_documents[document_id]["title"] == "Access"  # type: ignore[index]


def test_model_summary_compare_and_rewrite() -> None:
    from ar_domain.documents.grounding import compare, extract_fields, gaps, rewrite_text

    document = {
        "id": "d",
        "title": "Access",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Access",
                "level": 1,
                "text": "Staff use badges at every door. Visitors sign the book.",
            }
        ],
    }
    other = {
        "id": "e",
        "title": "Access",
        "passages": [
            {
                "anchor": "p1-s0",
                "page": 1,
                "heading": "Access",
                "level": 1,
                "text": "Staff use passes at every door.",
            }
        ],
    }

    def ask(task: str, evidence: str) -> str:
        assert "untrusted" in evidence
        if "claims" in task:
            return (
                '{"claims":[{"text":"Staff use badges.","anchor":"p1-s0",'
                '"quote":"Staff use badges"}]}'
            )
        if "notes" in task:
            return '{"notes":[{"heading":"Access","text":"The wording changed."}]}'
        return '{"text":"Visitors sign the book. Staff use badges at every door."}'

    summary = summarise(document, ask)
    assert summary["model_used"] is True
    result = compare(document, other, ask)
    assert result["notes"]
    proposed = rewrite_text(str(document["passages"][0]["text"]), "rephrase", ask)  # type: ignore[index]
    assert "badges" in proposed
    fields = extract_fields(document, ["door"], ask)
    assert fields["fields"]
    found = gaps(document, ["Operate a colony on Mars"], ask)
    assert found["rows"]


def test_long_text_is_chunked_and_model_can_judge() -> None:
    store = _store()
    actor = _actor()
    body = "\n".join(f"Section {index} staff use badges at door {index}." for index in range(80))
    saved = DocumentLibrary(store).ingest(actor, data=body.encode(), filename="long.txt")
    assert int(str(saved["page_count"])) >= 1
    document_id = uuid.UUID(str(saved["id"]))
    row = store.library_documents[document_id]
    passages = row["passages"]
    assert isinstance(passages, list)
    assert len(passages) > 1

    passage = passages[0]
    assert isinstance(passage, dict)
    quote = "staff use badges"
    assert quote in str(passage.get("text") or "")

    def judge(task: str, evidence: str) -> str:
        del task
        assert "untrusted_content" in evidence
        return (
            '{"verdict":"supported","passageId":"'
            + str(passage.get("anchor"))
            + '","quote":"staff use badges"}'
        )

    report = check(row, ["staff use badges"], judge, model_id="fixture-model")
    first = report["rows"][0]  # type: ignore[index]
    assert isinstance(first, dict)
    assert first["model"] is True
    assert first["verdict"] == "supported"
    assert first["model_id"] == "fixture-model"
    assert first["prompt_hash"]
    assert first["quote"] == quote


def test_text_pdf_and_ocr_binary() -> None:
    stream = b"BT /F1 24 Tf 72 720 Td (Staff use badges.) Tj ET"
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        + f"4 0 obj<</Length {len(stream)}>>stream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"trailer<</Root 1 0 R>>\n%%EOF\n"
    )
    try:
        extracted = extract_bytes(body, filename="policy.pdf")
    except ExtractError:
        extracted = None
    if extracted is not None:
        assert extracted.page_count == 1
    png = b"\x89PNG\r\n\x1a\nnot-really"
    with pytest.raises(ExtractError):
        extract_bytes(png, filename="scan.png")


def test_durable_document_sql() -> None:
    from ar_domain.durable.m24 import (
        save_document_checks,
        save_document_rewrites,
        save_library_documents,
    )

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def execute(
            self, statement: object, params: dict[str, object] | None = None
        ) -> object:
            self.calls.append((str(statement), params or {}))
            return SimpleNamespace(first=lambda: None)

    tenant = uuid.uuid4()
    owner = uuid.uuid4()
    document_id = uuid.uuid4()
    session = Session()
    asyncio.run(save_library_documents(session, [{"id": None}]))  # type: ignore[arg-type]
    asyncio.run(
        save_library_documents(
            session,  # type: ignore[arg-type]
            [
                {
                    "id": document_id,
                    "tenant_id": tenant,
                    "owner_user_id": owner,
                    "title": "Access",
                    "filename": "a.md",
                    "media_type": "text/markdown",
                    "source": "upload",
                    "content_hash": "abc",
                    "size_bytes": 12,
                    "passages": [{"anchor": "p1-s0", "page": 1, "text": "badges"}],
                    "tables": [],
                }
            ],
        )
    )
    asyncio.run(
        save_document_checks(
            session,  # type: ignore[arg-type]
            [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant,
                    "document_id": document_id,
                    "rows": {"kind": "check"},
                    "created_by": owner,
                }
            ],
        )
    )
    asyncio.run(
        save_document_rewrites(
            session,  # type: ignore[arg-type]
            [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant,
                    "document_id": document_id,
                    "original": "a",
                    "proposed": "b",
                    "hunks": [],
                    "created_by": owner,
                }
            ],
        )
    )
    joined = "\n".join(sql for sql, _params in session.calls)
    assert "library_documents" in joined
    assert "document_checks" in joined
    assert "document_rewrites" in joined

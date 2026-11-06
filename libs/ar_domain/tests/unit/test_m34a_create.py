"""Office create: DOCX, PDF and XLSX smoke files, plus DOCX and PPTX read-back."""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest
from pypdf import PdfReader

from ar_common.errors import NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.documents.create import parse, render
from ar_domain.documents.create.spec import CreateError
from ar_domain.documents.extract import extract_bytes
from ar_domain.documents.library import DocumentLibrary
from ar_domain.tools.documents import dispatch_documents
from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store
from ar_testing.objects import MemoryObjectStore

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "m34a"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_BRIEF: dict[str, object] = {
    "title": "Q3 regional brief",
    "subtitle": "Prepared for the board",
    "author": "Revenue desk",
    "template": "report",
    "sections": [
        {
            "heading": "Summary",
            "level": 1,
            "paragraphs": ["Revenue grew in two regions. The R&D café in Pune stayed open."],
            "bullets": ["EMEA added four points.", "APAC held flat."],
            "table": {
                "caption": "Regions",
                "columns": ["Region", "Change"],
                "rows": [["EMEA", "4%"], ["APAC", "0%"]],
            },
        },
        {
            "heading": "Next steps",
            "level": 2,
            "paragraphs": ["Confirm the hiring plan before the October review."],
        },
    ],
    "sheets": [
        {
            "name": "Regions",
            "columns": ["Region", "Change"],
            "rows": [["EMEA", 4], ["APAC", 0], ["R&D café", 1.5]],
        }
    ],
}


def _store() -> Any:
    class Store:
        def __init__(self) -> None:
            self.files: dict[uuid.UUID, dict[str, object]] = {}
            self.blobs: dict[uuid.UUID, bytes] = {}
            self.versions: dict[uuid.UUID, dict[str, object]] = {}
            self.runs: dict[uuid.UUID, dict[str, object]] = {}
            self.scanner = "none"
            self.audit_log: list[dict[str, object]] = []
            self.objects = MemoryObjectStore()

    return Store()


def _call(fmt: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = dict(_BRIEF)
    payload["format"] = fmt
    payload.update(extra)
    return payload


def test_render_is_deterministic_and_matches_golden_smoke_files() -> None:
    for fmt, name in (
        ("docx", "q3-brief.docx"),
        ("pdf", "q3-brief.pdf"),
        ("xlsx", "q3-brief.xlsx"),
    ):
        first = render(parse(_call(fmt)))
        second = render(parse(_call(fmt)))
        assert first == second
        assert len(first) > 200
        assert first == (_FIXTURES / name).read_bytes()


def test_docx_smoke_has_styles_heading_table_and_unicode() -> None:
    data = render(parse(_call("docx")))
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        names = set(book.namelist())
        assert "word/document.xml" in names
        assert "word/styles.xml" in names
        assert "word/numbering.xml" in names
        document = book.read("word/document.xml").decode()
    assert "Heading1" in document
    assert "Heading2" in document
    assert "R&amp;D café" in document
    extracted = extract_bytes(data, filename="q3-brief.docx")
    text = "\n".join(row.text for row in extracted.passages)
    assert "Summary" in text
    assert "R&D café" in text
    assert "EMEA added four points." in text
    assert extracted.tables
    assert "EMEA" in extracted.tables[0].csv_text
    assert "4%" in extracted.tables[0].csv_text


def test_pdf_smoke_opens_in_pypdf_and_extract() -> None:
    data = render(parse(_call("pdf")))
    assert data.startswith(b"%PDF-1.4")
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 1
    assert reader.metadata is not None
    assert reader.metadata.title == "Q3 regional brief"
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Summary" in text
    assert "Revenue grew" in text
    assert "R&D café" in text
    assert "EMEA" in text
    extracted = extract_bytes(data, filename="q3-brief.pdf")
    assert extracted.page_count >= 1
    assert "Summary" in extracted.passages[0].text or any(
        "Summary" in row.text for row in extracted.passages
    )


def test_xlsx_smoke_has_styles_shared_strings_numbers_and_unicode() -> None:
    data = render(parse(_call("xlsx")))
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        shared = book.read("xl/sharedStrings.xml").decode()
        sheet = book.read("xl/worksheets/sheet1.xml").decode()
        styles = book.read("xl/styles.xml").decode()
        workbook = book.read("xl/workbook.xml").decode()
    assert "EMEA" in shared
    assert "R&amp;D café" in shared
    assert 't="s"' in sheet
    assert "<v>4</v>" in sheet
    assert "1F4E79" in styles
    assert 'state="frozen"' in sheet
    assert "Regions" in workbook
    extracted = extract_bytes(data, filename="q3-brief.xlsx")
    csv_text = extracted.tables[0].csv_text
    assert "EMEA" in csv_text
    assert "4" in csv_text
    assert "café" in csv_text


def test_sections_become_a_workbook_and_sheets_become_a_document() -> None:
    sheetless = dict(_BRIEF)
    sheetless.pop("sheets")
    book = extract_bytes(render(parse({**sheetless, "format": "xlsx"})), filename="notes.xlsx")
    joined = " ".join(table.csv_text for table in book.tables)
    assert "EMEA" in joined
    assert "Confirm the hiring plan" in joined
    sectionless = dict(_BRIEF)
    sectionless.pop("sections")
    document = extract_bytes(
        render(parse({**sectionless, "format": "docx"})), filename="from-sheet.docx"
    )
    assert document.tables
    assert "café" in document.tables[0].csv_text


def test_brief_template_omits_the_running_header() -> None:
    report = render(parse(_call("docx")))
    brief = render(parse(_call("docx", template="brief", fileName="brief.docx")))
    with zipfile.ZipFile(io.BytesIO(report)) as book:
        assert "word/header1.xml" in book.namelist()
    with zipfile.ZipFile(io.BytesIO(brief)) as book:
        assert "word/header1.xml" not in book.namelist()
    assert extract_bytes(brief, filename="brief.docx").passages


def test_create_rejects_bad_payloads() -> None:
    with pytest.raises(CreateError, match="format"):
        parse({"title": "Note"})
    with pytest.raises(CreateError, match="title"):
        parse({"format": "pdf", "title": "  "})
    with pytest.raises(CreateError, match="500"):
        parse(
            {
                "format": "xlsx",
                "title": "Too big",
                "sheets": [
                    {"name": "Data", "columns": ["N"], "rows": [[index] for index in range(501)]}
                ],
            }
        )
    with pytest.raises(CreateError, match="sections"):
        parse({"format": "docx", "title": "Note", "sections": "nope"})


def test_tool_saves_a_downloadable_workspace_file() -> None:
    from ar_domain.tools.general import dispatch_general

    store = _store()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    run = uuid.uuid4()
    args = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_run_id": run,
        **_call("xlsx", fileName="../secrets.xlsx"),
    }
    created = dispatch(store, "builtin://documents", "create", args, "")
    assert created["is_error"] is False
    presentation = created["structured"]["presentation"]
    assert presentation["kind"] == "file"
    assert presentation["format"] == "xlsx"
    assert str(presentation["path"]).endswith("/workspace/outputs/secrets.xlsx")
    saved = presentation["files"][0]
    file_id = uuid.UUID(str(saved["file_id"]))
    blob = store.blobs[file_id]
    assert blob.startswith(b"PK")
    assert store.files[file_id]["tenant_id"] == tenant
    assert store.files[file_id]["kind"] == "artifact"
    assert store.files[file_id]["mime_type"].endswith("spreadsheetml.sheet")
    inspected = dispatch_general(store, "inspect_table", {**args, "path": presentation["path"]})
    assert inspected["is_error"] is False
    assert "Change number" in str(inspected["text"])
    sample = inspected["structured"]["presentation"]["sheets"][0]["sample"]
    assert sample[0][0] == "EMEA"
    assert sample[2][0] == "R&D café"
    missing = dispatch_documents(store, "create", {"format": "pdf", "title": "Orphan"})
    assert missing["code"] == "validation_failed"


def test_created_docx_round_trips_and_hides_from_another_tenant() -> None:
    store = _store()
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    actor = Actor(tenant_id=tenant, user_id=user, permissions=frozenset({"chat:use"}))
    created = dispatch_documents(
        store,
        "create",
        {"_tenant_id": tenant, "_user_id": user, "_run_id": uuid.uuid4(), **_call("docx")},
    )
    file_id = uuid.UUID(str(created["structured"]["presentation"]["files"][0]["file_id"]))
    library = DocumentLibrary(store)
    saved = library.ingest(
        actor, data=store.blobs[file_id], filename="q3-brief.docx", source="workspace"
    )
    document_id = uuid.UUID(str(saved["id"]))
    body = library.read(actor, document_id)
    assert "Summary" in str(body["text"])
    assert "café" in str(body["text"])
    tables = library.tables(actor, document_id)
    assert "4%" in str(tables)
    outsider = Actor(
        tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset({"chat:use"})
    )
    with pytest.raises(NotFoundError):
        library.read(outsider, document_id)


def test_pdf_and_xlsx_ingest_as_library_documents() -> None:
    store = _store()
    actor = Actor(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), permissions=frozenset())
    library = DocumentLibrary(store)
    for fmt in ("pdf", "xlsx"):
        data = render(parse(_call(fmt)))
        saved = library.ingest(actor, data=data, filename=f"q3-brief.{fmt}")
        assert saved["status"] == "ready"
        assert int(str(saved["page_count"])) >= 1


def test_pptx_and_docx_readers_keep_slide_and_heading_text() -> None:
    """Fixture canary for the M24 readers. This is not a live Office application."""
    slides = _pptx()
    deck = extract_bytes(slides, filename="roadmap.pptx")
    assert deck.page_count == 2
    combined = "\n".join(row.text for row in deck.passages)
    assert "Roadmap" in combined
    assert "Ship the reader in spring." in combined
    assert "Keep credentials out of the file." in combined
    docx = render(parse(_call("docx")))
    read = extract_bytes(docx, filename="q3-brief.docx")
    outline = [row.heading for row in read.passages]
    assert any(heading for heading in outline)
    assert "Next steps" in " ".join(row.text for row in read.passages)


def test_documents_create_is_seeded_as_a_write() -> None:

    store = demo_store()
    row = next(
        item
        for item in store.tool_versions.values()
        if item.get("qualified_name") == "documents.create"
    )
    assert row["risk_class"] == "W1"
    schema = row["input_schema"]
    assert schema["properties"]["format"]["enum"] == ["docx", "pdf", "xlsx"]
    assert "DOCX" in str(row["description"])


def _pptx() -> bytes:
    slide_1 = (
        f'<p:sld xmlns:a="{_A}" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:sp><p:txBody><a:p><a:r><a:t>Roadmap</a:t></a:r></a:p>"
        "<a:p><a:r><a:t>Ship the reader in spring.</a:t></a:r></a:p></p:txBody></p:sp></p:sld>"
    )
    slide_2 = (
        f'<p:sld xmlns:a="{_A}" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:sp><p:txBody><a:p><a:r><a:t>Risks</a:t></a:r></a:p>"
        "<a:p><a:r><a:t>Keep credentials out of the file.</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:sld>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("ppt/slides/slide1.xml", slide_1)
        book.writestr("ppt/slides/slide2.xml", slide_2)
    return buffer.getvalue()


def test_created_package_xml_parses() -> None:
    for fmt, part in (
        ("docx", "word/document.xml"),
        ("xlsx", "xl/worksheets/sheet1.xml"),
    ):
        data = render(parse(_call(fmt)))
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            ET.fromstring(book.read(part))  # noqa: S314 — fixture produced by this package

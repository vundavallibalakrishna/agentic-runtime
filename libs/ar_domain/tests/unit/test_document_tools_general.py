"""General document tools. Behaviour comes from the instruction and the schema."""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest

from ar_domain.documents.cited import _ANCHOR
from ar_domain.documents.create.redline import render_version
from ar_domain.documents.extract import extract_bytes
from ar_domain.documents.library import DocumentLibrary
from ar_domain.documents.strategy import documents_fit, estimate_tokens

ROOT = Path(__file__).resolve().parents[2] / "src" / "ar_domain" / "documents"


def test_the_citation_pattern_matches_a_table_anchor() -> None:
    assert _ANCHOR.findall("see [t3 p.2] and [p4-s1]") == ["t3", "p4-s1"]


def test_a_spreadsheet_keeps_the_sheet_name() -> None:
    data = _xlsx({"Obligations": [["Item", "Owner"], ["File the return", "Ada"]]})
    extracted = extract_bytes(data, filename="book.xlsx")
    assert extracted.tables[0].caption == "Obligations"
    assert "File the return" in extracted.tables[0].csv_text


def test_an_edit_writes_a_new_file_and_leaves_the_original() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    original = library.ingest(actor, data=b"# One\n\nAlpha.\n", filename="note.md")
    document_id = uuid.UUID(str(original["id"]))
    before = store.library_documents[document_id]["passages"][0]["text"]
    anchor = store.library_documents[document_id]["passages"][0]["anchor"]
    created = library.edit(actor, document_id, [{"anchor": anchor, "text": "Beta."}], redline=True)
    assert created["id"] != str(document_id)
    assert store.library_documents[document_id]["passages"][0]["text"] == before
    assert render_version(
        [{"anchor": "p1-s0", "text": "Alpha."}],
        [{"anchor": "p1-s0", "text": "Beta."}],
        redline=True,
    )


def test_a_new_version_keeps_headings_looking_like_headings() -> None:
    import io
    import zipfile

    passages = [
        {"anchor": "p1-s0", "text": "Agreement", "heading": "Agreement", "level": 1},
        {"anchor": "p1-s1", "text": "5. Breach notice", "heading": "5. Breach notice", "level": 2},
        {
            "anchor": "p1-s2",
            "text": "Notice within 7 days.",
            "heading": "5. Breach notice",
            "level": 2,
        },
    ]
    data = render_version(
        passages, [{"anchor": "p1-s2", "text": "Notice within 48 hours."}], redline=True
    )
    body = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode()
    title, section, clause = body.split("<w:p>")[1:4]
    assert '<w:b/><w:sz w:val="32"/>' in title
    assert '<w:b/><w:sz w:val="26"/>' in section
    # The clause is body text, and its change is tracked, not styled.
    assert "<w:b/>" not in clause
    assert "<w:del " in clause
    assert "<w:ins " in clause


def test_read_returns_a_cursor_when_the_text_is_longer_than_the_limit() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    body = "word " * 4000
    created = library.ingest(actor, data=body.encode(), filename="long.txt")
    first = library.read(actor, uuid.UUID(str(created["id"])), limit=100)
    assert first["nextCursor"]
    second = library.read(
        actor, uuid.UUID(str(created["id"])), cursor=str(first["nextCursor"]), limit=100
    )
    assert second["text"]
    assert second["text"] != first["text"]


def test_measured_facts_say_whether_one_file_fits() -> None:
    short = estimate_tokens("hello")
    from ar_domain.documents.strategy import NamedText

    fits, usable = documents_fit(
        [NamedText(file_id="f", document_id="d", tokens=short, characters=5, headings=0)],
        32_768,
    )
    assert fits
    assert usable is not None


def test_map_stores_a_result_a_follow_up_can_retrieve() -> None:
    from ar_domain.documents.sections import begin_map, deliver_map, run_section
    from ar_domain.loop.context import read_output

    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    saved = library.ingest(
        actor, data=b"# Hours\n\nThe desk opens at eight.\n", filename="hours.md"
    )
    run = {
        "id": uuid.uuid4(),
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "conversation_id": uuid.uuid4(),
        "checkpoint": {},
    }
    store.runs = {run["id"]: run}
    store.conversations = {run["conversation_id"]: {}}
    begin_map(
        store,
        run,
        {"instruction": "Say when the desk opens.", "documentIds": [str(saved["id"])]},
    )
    section = run["checkpoint"]["document_map"]["sections"][0]

    def model(store, run, job, section, text):  # type: ignore[no-untyped-def]
        del store, run, job, section, text
        return "Opens at eight."

    from ar_domain.documents import sections as mod

    original = mod._read_model
    mod._read_model = model  # type: ignore[assignment]
    try:
        run_section(store, run, section)
    finally:
        mod._read_model = original
    body = deliver_map(store, run)
    assert body["results"][0]["output"] == "Opens at eight."
    assert read_output(run, str(body["outputId"]))


def test_created_files_include_markdown_html_and_csv() -> None:
    from ar_domain.documents.create.render import render
    from ar_domain.documents.create.spec import parse

    spec = parse(
        {
            "format": "md",
            "title": "Notes",
            "sections": [{"heading": "One", "paragraphs": ["Hello"]}],
        }
    )
    assert b"# Notes" in render(spec)
    html = parse({"format": "html", "title": "Notes", "sections": [{"heading": "One"}]})
    assert b"<h1>Notes</h1>" in render(html)
    csv = parse(
        {
            "format": "csv",
            "title": "Notes",
            "sheets": [{"name": "A", "columns": ["n"], "rows": [["1"]]}],
        }
    )
    assert b"n" in render(csv)


def test_email_and_zip_use_the_same_extractor() -> None:
    from ar_domain.documents.convert import convert_and_extract

    message = b"Subject: Hours\nFrom: ada@example.com\n\nThe desk opens at eight.\n"
    extracted = convert_and_extract(message, "note.eml", "message/rfc822")
    assert any("desk" in passage.text for passage in extracted.passages)
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("note.txt", "The desk opens at eight.")
    packed = convert_and_extract(buffer.getvalue(), "notes.zip", "application/zip")
    assert any("desk" in passage.text for passage in packed.passages)


def test_extract_without_a_model_is_an_error() -> None:
    store = _store()
    library = DocumentLibrary(store)
    actor = _actor()
    saved = library.ingest(actor, data=b"The desk opens at eight.\n", filename="hours.txt")
    from ar_common.errors import ArError

    with pytest.raises(ArError):
        library.extract(
            actor,
            uuid.UUID(str(saved["id"])),
            {"type": "object", "properties": {"when": {"type": "string"}}},
        )


def test_documents_has_no_task_enum_or_keyword_branch() -> None:
    banned = ("summarise", "compare", "crosscheck", "judge", "missing", "rewrite", "redact")
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "Enum" for base in node.bases
            ):
                pytest.fail(f"{path.name} declares an Enum")
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                if node.value.id == "Literal":
                    pytest.fail(f"{path.name} uses Literal")
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant):
                if isinstance(node.left.value, str) and node.left.value in banned:
                    pytest.fail(f"{path.name} branches on {node.left.value}")


def _store() -> object:
    from types import SimpleNamespace

    return SimpleNamespace(
        library_documents={},
        files={},
        audit_log=[],
        scanner="none",
        versions={},
        knowledge_documents={},
        knowledge_collections={},
    )


def _actor() -> object:
    from ar_domain.agents.access import Actor
    from ar_domain.identity.permissions import PERMISSION_KEYS

    return Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)


def _xlsx(sheets: dict[str, list[list[str]]]) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Override PartName="/xl/workbook.xml"
                ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
            </Types>""",
        )
        book.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <sheets><sheet name="Obligations" sheetId="1" r:id="rId1"/></sheets>
            </workbook>""",
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
                Target="worksheets/sheet1.xml"/>
            </Relationships>""",
        )
        rows = sheets["Obligations"]
        cells = []
        for row_index, row in enumerate(rows, start=1):
            row_xml = "".join(
                f'<c r="{chr(65 + col)}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>'
                for col, value in enumerate(row)
            )
            cells.append(f'<row r="{row_index}">{row_xml}</row>')
        book.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>"""
            + "".join(cells)
            + """</sheetData></worksheet>""",
        )
    return buffer.getvalue()

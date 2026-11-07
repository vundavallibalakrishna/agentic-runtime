"""M34b: DuckDB sheet SQL, questionnaire write-back, chart themes and a slide."""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ar_domain.demo_ids import demo_id
from ar_domain.documents.create import parse, render
from ar_domain.documents.extract import extract_bytes
from ar_domain.skills.book import SkillBook
from ar_domain.spreadsheet.grid import grids_from_xlsx
from ar_domain.spreadsheet.skill import INSTRUCTIONS, SLUG
from ar_domain.tools.charts import render_chart
from ar_domain.tools.documents import dispatch_documents
from ar_domain.tools.general import _prepare, dispatch_general
from ar_domain.tools.sql_guard import SqlRejected, check_sql
from ar_testing.demo import demo_store
from ar_testing.showcase.skills import seed_composition

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "m34a"


def _args() -> tuple[ChatService, dict[str, object]]:
    store = demo_store()
    arguments: dict[str, object] = {
        "_run_id": uuid.uuid4(),
        "_tenant_id": uuid.uuid4(),
        "_user_id": uuid.uuid4(),
    }
    return store, arguments


def test_duckdb_sums_orders_joins_and_rejects_file_scans(tmp_path: Path) -> None:
    store, arguments = _args()
    root = _prepare(store, arguments)
    inputs = root / "workspace" / "inputs"
    (inputs / "ranks.csv").write_text("state,stores\nA,9\nB,10\n", encoding="utf-8")
    (inputs / "cities.csv").write_text("state,city\nB,Austin\nA,Dallas\n", encoding="utf-8")
    ordered = dispatch_general(
        store,
        "query_table",
        {**arguments, "path": "ranks.csv", "sql": "SELECT state FROM ranks ORDER BY stores DESC"},
    )
    assert ordered["is_error"] is False
    presentation = ordered["structured"]["presentation"]
    assert presentation["engine"] == "duckdb"
    assert presentation["rows"][0][0] == "B"
    total = dispatch_general(
        store,
        "query_table",
        {**arguments, "path": "ranks.csv", "sql": "SELECT SUM(stores) AS total FROM ranks"},
    )
    assert total["is_error"] is False
    assert "19" in str(total["text"])
    joined = dispatch_general(
        store,
        "query_table",
        {
            **arguments,
            "paths": ["ranks.csv", "cities.csv"],
            "sql": (
                "SELECT ranks.state, cities.city FROM ranks "
                "JOIN cities ON ranks.state = cities.state WHERE ranks.state = 'B'"
            ),
        },
    )
    assert joined["is_error"] is False
    assert "Austin" in str(joined["text"])
    sentinel = tmp_path / "sentinel.csv"
    sentinel.write_text("secret,value\nLEAK,1\n", encoding="utf-8")
    leaked = dispatch_general(
        store,
        "query_table",
        {
            **arguments,
            "path": "ranks.csv",
            "sql": f"SELECT * FROM read_csv('{sentinel}')",  # noqa: S608
        },
    )
    assert leaked["is_error"] is True
    assert leaked["code"] == "sql_rejected"
    assert "LEAK" not in str(leaked)
    installed = dispatch_general(
        store,
        "query_table",
        {**arguments, "path": "ranks.csv", "sql": "INSTALL httpfs"},
    )
    assert installed["code"] == "sql_rejected"
    with pytest.raises(SqlRejected):
        check_sql(
            "SELECT read_csv('/etc/passwd')",
            allow_tables=set(),
            deny_columns=set(),
            dialect="duckdb",
            allow_any=True,
        )


def test_pivot_table_sums_across_a_column() -> None:
    store, arguments = _args()
    root = _prepare(store, arguments)
    (root / "workspace" / "inputs" / "sales.csv").write_text(
        "region,product,amount\nN,pen,10\nN,ink,5\nS,pen,2\n",
        encoding="utf-8",
    )
    pivoted = dispatch_general(
        store,
        "pivot_table",
        {**arguments, "path": "sales.csv", "index": "region", "on": "product", "value": "amount"},
    )
    assert pivoted["is_error"] is False
    presentation = pivoted["structured"]["presentation"]
    assert presentation["kind"] == "pivot"
    assert presentation["engine"] == "duckdb"
    by_region = {row[0]: row for row in presentation["rows"]}
    columns = presentation["columns"]
    pen = columns.index("pen")
    ink = columns.index("ink")
    assert by_region["N"][pen] == 10
    assert by_region["N"][ink] == 5
    assert by_region["S"][pen] == 2


def test_questionnaire_writes_answers_and_grounds_a_document() -> None:
    store, arguments = _args()
    root = _prepare(store, arguments)
    book = render(
        parse(
            {
                "format": "xlsx",
                "title": "CAIQ",
                "sheets": [
                    {
                        "name": "CAIQ",
                        "columns": ["Question ID", "Question", "Answer", "Notes"],
                        "rows": [
                            ["CAIQ-1", "Do you encrypt data at rest?", "", ""],
                            ["CAIQ-2", "Is the cafeteria open on Sunday?", "", ""],
                        ],
                    }
                ],
            }
        )
    )
    (root / "workspace" / "inputs" / "caiq.xlsx").write_bytes(book)
    filled = dispatch_documents(
        store,
        "fill_questionnaire",
        {
            **arguments,
            "path": "caiq.xlsx",
            "fileName": "caiq-filled.xlsx",
            "answers": [
                {
                    "id": "CAIQ-1",
                    "answer": "Yes. Data at rest uses AES.",
                    "notes": "See the policy.",
                    "citation": "policy p-1",
                }
            ],
        },
    )
    assert filled["is_error"] is False
    presentation = filled["structured"]["presentation"]
    assert presentation["filled"] == 1
    assert presentation["unanswered"] == 1
    blob = store.blobs[uuid.UUID(presentation["files"][0]["file_id"])]
    grid = next(item for item in grids_from_xlsx(blob) if item.name == "CAIQ")
    header = list(grid.columns)
    answer = header.index("Answer")
    status = header.index("Status")
    by_id = {row[0]: row for row in grid.rows}
    assert "AES" in by_id["CAIQ-1"][answer]
    assert by_id["CAIQ-1"][status] == "provided"
    assert by_id["CAIQ-2"][answer] == ""
    assert by_id["CAIQ-2"][status] == "unanswered"
    tenant = arguments["_tenant_id"]
    assert isinstance(tenant, uuid.UUID)
    document_id = uuid.uuid4()
    store.library_documents[document_id] = {
        "id": document_id,
        "tenant_id": tenant,
        "title": "Security policy",
        "passages": [
            {
                "anchor": "p-1",
                "page": 1,
                "heading": "Encryption",
                "text": "We encrypt data at rest with AES-256.",
            }
        ],
    }
    grounded = dispatch_documents(
        store,
        "fill_questionnaire",
        {
            **arguments,
            "path": "caiq.xlsx",
            "documentId": str(document_id),
            "fileName": "grounded.xlsx",
        },
    )
    assert grounded["is_error"] is False
    grounded_blob = store.blobs[
        uuid.UUID(grounded["structured"]["presentation"]["files"][0]["file_id"])
    ]
    grounded_grid = next(item for item in grids_from_xlsx(grounded_blob) if item.name == "CAIQ")
    grounded_answer = list(grounded_grid.columns).index("Answer")
    grounded_rows = {row[0]: row for row in grounded_grid.rows}
    assert "AES-256" in grounded_rows["CAIQ-1"][grounded_answer]
    assert grounded_rows["CAIQ-2"][grounded_answer] == ""
    other = dispatch_documents(
        store,
        "fill_questionnaire",
        {
            **arguments,
            "_tenant_id": uuid.uuid4(),
            "path": "caiq.xlsx",
            "documentId": str(document_id),
        },
    )
    assert other["is_error"] is True
    assert other["code"] == "not_found"
    assert "AES-256" not in str(other)


def test_chart_themes_area_and_slide_round_trip() -> None:
    rows = [("North", 4.0), ("South", 2.0), ("West", 3.0)]
    ink = render_chart("bar", rows, theme="ink")
    forest = render_chart("bar", rows, theme="forest")
    midnight = render_chart("bar", rows, theme="midnight")
    assert ink.startswith(b"\x89PNG")
    assert len({ink, forest, midnight}) == 3
    area = render_chart("area", rows)
    line = render_chart("line", rows)
    assert area != line
    store, arguments = _args()
    drawn = dispatch_general(
        store,
        "chart",
        {
            **arguments,
            "kind": "area",
            "theme": "midnight",
            "title": "Regional trend",
            "narrative": "West sits between the other two regions.",
            "slide": True,
            "rows": [{"label": label, "value": value} for label, value in rows],
        },
    )
    assert drawn["is_error"] is False
    presentation = drawn["structured"]["presentation"]
    assert presentation["theme"] == "midnight"
    names = {item["name"] for item in presentation["files"]}
    assert names == {"chart.png", "chart.pptx"}
    deck = store.blobs[uuid.UUID(presentation["files"][1]["file_id"])]
    with zipfile.ZipFile(io.BytesIO(deck)) as book:
        assert book.read("ppt/media/chart.png").startswith(b"\x89PNG")
    extracted = extract_bytes(deck, filename="chart.pptx")
    text = "\n".join(row.text for row in extracted.passages)
    assert "Regional trend" in text
    assert "West sits between" in text
    refused = dispatch_general(
        store, "chart", {**arguments, "kind": "bar", "theme": "neon", "rows": [["A", 1]]}
    )
    assert refused["is_error"] is True


def test_docx_and_skill_canaries() -> None:
    docx = (_FIXTURES / "q3-brief.docx").read_bytes()
    extracted = extract_bytes(docx, filename="q3-brief.docx")
    text = "\n".join(row.text for row in extracted.passages)
    assert "Summary" in text
    assert "café" in text
    store = demo_store()
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    published = SkillBook(store).published_by_slug(demo_id("tenant"), SLUG)
    assert published is not None
    version = next(
        row
        for row in store.skill_versions.values()
        if isinstance(row, dict) and row.get("skill_id") == published["id"]
    )
    assert "documents.fill_questionnaire" in list(version["required_tools"])
    assert "unanswered" in str(version["instructions_md"]).lower()
    assert INSTRUCTIONS.split("\n", 1)[0] in str(version["instructions_md"])
    tool = next(
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "documents.fill_questionnaire"
    )
    assert tool["risk_class"] == "W1"
    chart = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "general.chart"
    )
    assert "midnight" in str(chart["description"])

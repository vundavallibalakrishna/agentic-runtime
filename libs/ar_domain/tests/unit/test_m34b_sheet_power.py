"""M34b: DuckDB sheet SQL, chart themes and a slide."""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ar_domain.documents.extract import extract_bytes
from ar_domain.tools.charts import render_chart
from ar_domain.tools.general import _prepare, dispatch_general
from ar_domain.tools.sql_guard import SqlRejected, check_sql
from ar_testing.demo import demo_store

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


def test_docx_canary() -> None:
    docx = (_FIXTURES / "q3-brief.docx").read_bytes()
    extracted = extract_bytes(docx, filename="q3-brief.docx")
    text = "\n".join(row.text for row in extracted.passages)
    assert "Summary" in text
    assert "café" in text

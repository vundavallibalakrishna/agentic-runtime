#!/usr/bin/env python
"""Exercise the document / spreadsheet / PDF / chart / OCR toolchain on REAL inputs.

Where the tool matrix (scripts/tool_matrix.py) proves every tool is *callable* with
schema-generated arguments, this proves the document tools actually *do real work*: each
case feeds a real input through the real ``ToolPipeline.execute`` path and asserts the real
output — a created PDF that pypdf reads back, a DuckDB sum that is correct, an OCR string
that matches, a chart that is a valid PNG. No model and no sandbox container are needed:
these tools run in-process (pypdf, duckdb, the tesseract binary, hand-rolled office writers).

Run:        uv run python scripts/document_toolchain.py
Guard mode: uv run python scripts/document_toolchain.py --check   # exit 1 on any failure

It writes docs/testing/document-toolchain/report.md and never prints secrets.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import uuid
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any  # noqa: TC003 - used at runtime in dataclass field annotations

import pypdf

from ar_domain.chat.service import demo_id
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

# A fixed run id per case gives its tool calls a shared workspace, so one case can write a
# file with one tool and read it with the next (the pipeline keys the run root off run_id).
PASS = "pass"  # noqa: S105 - an outcome label, not a credential
FAIL = "fail"
SKIP = "skip"  # a prerequisite (e.g. the tesseract binary) is absent on this host


@dataclass
class CaseResult:
    name: str
    tool: str
    status: str
    detail: str


@dataclass
class Harness:
    """Drives tools through the real pipeline and locates their workspace on disk."""

    store: Any
    pipeline: ToolPipeline
    by_name: dict[str, uuid.UUID] = field(default_factory=dict)
    tenant: uuid.UUID = field(default_factory=lambda: demo_id("tenant"))
    user: uuid.UUID = field(default_factory=lambda: demo_id("admin"))

    @classmethod
    def build(cls) -> Harness:
        store = demo_store()
        by_name: dict[str, uuid.UUID] = {}
        for row in store.tool_versions.values():
            qualified = row.get("qualified_name")
            if qualified:
                by_name[str(qualified)] = row["id"]
        return cls(store=store, pipeline=ToolPipeline(store), by_name=by_name)

    def call(
        self, qualified: str, arguments: Mapping[str, object], run_id: uuid.UUID
    ) -> dict[str, object]:
        request = {
            "tenant_id": self.tenant,
            "user_id": self.user,
            "run_id": run_id,
            "synthetic": True,
            "tool_version_id": self.by_name[qualified],
            "arguments": arguments,
            "model_call_id": f"toolchain-{qualified}-{run_id}",
        }
        return self.pipeline.execute(request)

    @staticmethod
    def workspace(run_id: uuid.UUID) -> Path:
        base = Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "ar-run-workspaces"
        return base / str(run_id) / "workspace"


def _succeeded(result: dict[str, object]) -> bool:
    return result.get("status") == "succeeded" and not result.get("is_error")


def _presentation(result: dict[str, object]) -> dict[str, object]:
    structured = result.get("structured")
    pres = structured.get("presentation") if isinstance(structured, dict) else None
    return pres if isinstance(pres, dict) else {}


def _first_file_id(result: dict[str, object]) -> uuid.UUID:
    files = _presentation(result).get("files")
    if not isinstance(files, list) or not files:
        raise AssertionError("no file in the tool result")
    return uuid.UUID(str(files[0]["file_id"]))


def _text(result: dict[str, object]) -> str:
    # The model-visible text on the pipeline path is `wrapped` (full) or `result_preview`.
    return str(result.get("wrapped") or result.get("result_preview") or "")


# --- cases -------------------------------------------------------------------------------
# Each case: (name, tool, fn) where fn(h) runs the tool(s) and returns (status, detail).
Case = Callable[[Harness], tuple[str, str]]
CASES: list[tuple[str, str, Case]] = []


def case(name: str, tool: str) -> Callable[[Case], Case]:
    def register(fn: Case) -> Case:
        CASES.append((name, tool, fn))
        return fn

    return register


# A real spreadsheet: six rows, two products across three regions. sum(amount) = 35.
_SALES_CSV = (
    "region,product,amount\n"
    "EMEA,pen,10\nEMEA,ink,5\n"
    "APAC,pen,7\nAPAC,ink,3\n"
    "AMER,pen,8\nAMER,ink,2\n"
)
_FIXTURES = Path("docs/testing/fixtures/m33b")  # ocr-canary.png lives here (committed)


def _put_input(run_id: uuid.UUID, name: str, text: str) -> None:
    inputs = Harness.workspace(run_id) / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    (inputs / name).write_text(text, encoding="utf-8")


def _attach(h: Harness, data: bytes, name: str, media: str) -> uuid.UUID:
    file_id = uuid.uuid4()
    h.store.blobs[file_id] = data
    h.store.files[file_id] = {"tenant_id": h.tenant, "name": name, "mime_type": media}
    return file_id


@case("python compute (6*7)", "general.code")
def _code(h: Harness) -> tuple[str, str]:
    r = h.call("general.code", {"source": "print(6 * 7)"}, uuid.uuid4())
    out = str(_presentation(r).get("stdout") or "")
    return (
        (PASS, f"stdout={out.strip()!r}")
        if _succeeded(r) and "42" in out
        else (FAIL, f"{_text(r)[:120]}")
    )


@case("bash compute (echo)", "general.shell")
def _shell(h: Harness) -> tuple[str, str]:
    r = h.call("general.shell", {"command": "echo $((6 * 7))"}, uuid.uuid4())
    out = str(_presentation(r).get("stdout") or "")
    return (
        (PASS, f"stdout={out.strip()!r}")
        if _succeeded(r) and "42" in out
        else (FAIL, _text(r)[:120])
    )


@case("write then read back a file", "general.write_file")
def _write_read(h: Harness) -> tuple[str, str]:
    run = uuid.uuid4()
    w = h.call("general.write_file", {"path": "note.txt", "content": "alpha\nbeta\ngamma\n"}, run)
    if not _succeeded(w):
        return FAIL, f"write: {_text(w)[:120]}"
    r = h.call("general.read_file", {"path": "note.txt", "offset": 1, "limit": 2}, run)
    got = str(_presentation(r).get("stdout") or _text(r))
    return (
        (PASS, f"read {got.strip()!r}")
        if "beta" in got and "gamma" in got
        else (FAIL, f"read={got[:120]!r}")
    )


@case("DuckDB SUM over a CSV", "general.query_table")
def _query(h: Harness) -> tuple[str, str]:
    run = uuid.uuid4()
    _put_input(run, "sales.csv", _SALES_CSV)
    r = h.call(
        "general.query_table",
        {"path": "sales.csv", "sql": "SELECT sum(amount) AS total FROM sales"},
        run,
    )
    rows = _presentation(r).get("rows")
    total = rows[0][0] if isinstance(rows, list) and rows and isinstance(rows[0], list) else None
    return (
        (PASS, f"sum(amount)={total}")
        if _succeeded(r) and str(total) == "35"
        else (FAIL, f"rows={rows} {_text(r)[:80]}")
    )


@case("inspect a CSV schema", "general.inspect_table")
def _inspect(h: Harness) -> tuple[str, str]:
    run = uuid.uuid4()
    _put_input(run, "sales.csv", _SALES_CSV)
    r = h.call("general.inspect_table", {"path": "sales.csv"}, run)
    sheets = _presentation(r).get("sheets")
    cols = [c["name"] for c in sheets[0]["columns"]] if isinstance(sheets, list) and sheets else []
    ok = _succeeded(r) and {"region", "product", "amount"} <= set(cols)
    return (PASS, f"columns={cols}") if ok else (FAIL, f"columns={cols} {_text(r)[:80]}")


@case("pivot region x product", "general.pivot_table")
def _pivot(h: Harness) -> tuple[str, str]:
    run = uuid.uuid4()
    _put_input(run, "sales.csv", _SALES_CSV)
    r = h.call(
        "general.pivot_table",
        {"path": "sales.csv", "index": "region", "on": "product", "value": "amount"},
        run,
    )
    pres = _presentation(r)
    cols, rows = pres.get("columns"), pres.get("rows")
    ok = (
        _succeeded(r)
        and isinstance(cols, list)
        and "pen" in cols
        and isinstance(rows, list)
        and rows
    )
    return (PASS, f"pivot columns={cols}") if ok else (FAIL, f"cols={cols} {_text(r)[:80]}")


@case("export rows to XLSX", "general.export_table")
def _export(h: Harness) -> tuple[str, str]:
    r = h.call(
        "general.export_table",
        {
            "format": "xlsx",
            "rows": [{"state": "TX", "stores": 315}, {"state": "FL", "stores": 175}],
        },
        uuid.uuid4(),
    )
    if not _succeeded(r):
        return FAIL, _text(r)[:120]
    blob = h.store.blobs[_first_file_id(r)]

    ok = blob[:2] == b"PK" and zipfile.is_zipfile(io.BytesIO(blob))
    return (
        (PASS, f"xlsx {len(blob)} bytes, valid zip") if ok else (FAIL, f"not a zip: {blob[:8]!r}")
    )


@case("render a bar chart PNG", "general.chart")
def _chart(h: Harness) -> tuple[str, str]:
    r = h.call(
        "general.chart",
        {
            "kind": "bar",
            "title": "Stores",
            "xKey": "state",
            "yKey": "stores",
            "rows": [{"state": "TX", "stores": 315}, {"state": "FL", "stores": 175}],
        },
        uuid.uuid4(),
    )
    if not _succeeded(r):
        return FAIL, _text(r)[:120]
    blob = h.store.blobs[_first_file_id(r)]
    ok = blob[:4] == b"\x89PNG" and len(blob) > 100
    return (PASS, f"PNG {len(blob)} bytes") if ok else (FAIL, f"not a PNG: {blob[:8]!r}")


@case("create a PDF, read it back", "documents.create")
def _create_pdf(h: Harness) -> tuple[str, str]:
    spec = {
        "format": "pdf",
        "title": "Revenue Summary",
        "template": "report",
        "sections": [
            {
                "heading": "Overview",
                "level": 1,
                "paragraphs": ["Canary DOCGEN7731 marks this report."],
            }
        ],
    }
    r = h.call("documents.create", spec, uuid.uuid4())
    if not _succeeded(r):
        return FAIL, _text(r)[:120]
    blob = h.store.blobs[_first_file_id(r)]
    if blob[:4] != b"%PDF":
        return FAIL, f"not a PDF: {blob[:8]!r}"

    text = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(blob)).pages)
    flat = text.replace(" ", "")
    return (
        (PASS, f"PDF {len(blob)}B, pypdf read the canary")
        if "DOCGEN7731" in flat
        else (FAIL, f"canary missing from {text[:80]!r}")
    )


@case("create a DOCX (valid OOXML)", "documents.create")
def _create_docx(h: Harness) -> tuple[str, str]:
    spec = {
        "format": "docx",
        "title": "Brief",
        "sections": [{"heading": "Point", "paragraphs": ["Canary DOCX5520 here."]}],
    }
    r = h.call("documents.create", spec, uuid.uuid4())
    if not _succeeded(r):
        return FAIL, _text(r)[:120]
    blob = h.store.blobs[_first_file_id(r)]

    if not zipfile.is_zipfile(io.BytesIO(blob)):
        return FAIL, f"not OOXML zip: {blob[:8]!r}"
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        body = zf.read("word/document.xml").decode("utf-8", "replace").replace(" ", "")
    return (
        (PASS, f"docx {len(blob)}B, canary in document.xml")
        if "DOCX5520" in body
        else (FAIL, "canary missing from document.xml")
    )


@case("create an XLSX (valid OOXML)", "documents.create")
def _create_xlsx(h: Harness) -> tuple[str, str]:
    spec = {
        "format": "xlsx",
        "title": "Numbers",
        "sheets": [
            {"name": "Regions", "columns": ["Region", "Change"], "rows": [["EMEA", 4], ["APAC", 0]]}
        ],
    }
    r = h.call("documents.create", spec, uuid.uuid4())
    if not _succeeded(r):
        return FAIL, _text(r)[:120]
    blob = h.store.blobs[_first_file_id(r)]

    ok = (
        zipfile.is_zipfile(io.BytesIO(blob))
        and "xl/workbook.xml" in zipfile.ZipFile(io.BytesIO(blob)).namelist()
    )
    return (
        (PASS, f"xlsx {len(blob)}B, has xl/workbook.xml")
        if ok
        else (FAIL, f"not a workbook: {blob[:8]!r}")
    )


@case("ingest a PDF, extract its text", "documents.ingest")
def _ingest_read(h: Harness) -> tuple[str, str]:
    run = uuid.uuid4()
    created = h.call(
        "documents.create",
        {
            "format": "pdf",
            "title": "Ingest Target",
            "sections": [{"heading": "Body", "paragraphs": ["Ingest canary INGEST9034."]}],
        },
        run,
    )
    if not _succeeded(created):
        return FAIL, f"create: {_text(created)[:100]}"
    file_id = _first_file_id(created)
    ing = h.call("documents.ingest", {"fileId": str(file_id)}, run)
    doc = _presentation(ing).get("document")
    doc_id = doc.get("id") if isinstance(doc, dict) else None
    if not _succeeded(ing) or not doc_id:
        return FAIL, f"ingest: {_text(ing)[:100]}"
    read = h.call("documents.read", {"documentId": str(doc_id)}, run)
    body = _text(read) + str(_presentation(read).get("text") or "")
    return (
        (PASS, f"ingested doc {str(doc_id)[:8]}, text round-trips")
        if "INGEST9034" in body.replace(" ", "")
        else (FAIL, f"canary missing from read: {body[:100]!r}")
    )


@case("extract a table from a document", "documents.tables")
def _tables(h: Harness) -> tuple[str, str]:
    run = uuid.uuid4()
    created = h.call(
        "documents.create",
        {
            "format": "docx",
            "title": "Table Target",
            "sections": [
                {
                    "heading": "Regions",
                    "table": {
                        "caption": "Regions",
                        "columns": ["Region", "Change"],
                        "rows": [["EMEA", "4%"], ["APAC", "0%"]],
                    },
                }
            ],
        },
        run,
    )
    if not _succeeded(created):
        return FAIL, f"create: {_text(created)[:100]}"
    ing = h.call("documents.ingest", {"fileId": str(_first_file_id(created))}, run)
    doc = _presentation(ing).get("document")
    doc_id = doc.get("id") if isinstance(doc, dict) else None
    if not _succeeded(ing) or not doc_id:
        return FAIL, f"ingest: {_text(ing)[:100]}"
    r = h.call("documents.tables", {"documentId": str(doc_id)}, run)
    tables = _presentation(r).get("tables")
    body = _text(r) + (str(tables) if tables else "")
    flat = body.replace(" ", "")
    ok = _succeeded(r) and "EMEA" in flat and "APAC" in flat
    return (
        (PASS, f"{len(tables) if isinstance(tables, list) else 0} table(s), cells round-trip")
        if ok
        else (FAIL, f"tables={body[:120]!r}")
    )


@case("real OCR of a scanned image", "documents.ocr")
def _ocr(h: Harness) -> tuple[str, str]:

    if not shutil.which("tesseract"):
        return SKIP, "tesseract binary not installed on this host"
    png = _FIXTURES / "ocr-canary.png"
    if not png.exists():
        return SKIP, f"fixture missing: {png}"
    file_id = _attach(h, png.read_bytes(), "ocr-canary.png", "image/png")
    r = h.call("documents.ocr", {"fileId": str(file_id), "engine": "tesseract"}, uuid.uuid4())
    body = _text(r) + str(_presentation(r).get("document") or "")
    flat = body.upper().replace(" ", "")
    ok = _succeeded(r) and "CANARY" in flat and "4821" in flat
    return (PASS, "tesseract read CANARY / 4821") if ok else (FAIL, f"ocr text={body[:120]!r}")


# --- runner ------------------------------------------------------------------------------
def run(*, check: bool = False) -> int:
    h = Harness.build()
    results: list[CaseResult] = []
    for name, tool, fn in CASES:
        try:
            status, detail = fn(h)
        except Exception as exc:  # noqa: BLE001 - a crash is a failure, recorded not raised
            status, detail = FAIL, f"raised {type(exc).__name__}: {exc}"[:200]
        results.append(CaseResult(name, tool, status, detail))
        print(f"  [{status.upper():4}] {name} ({tool}) — {detail}")
    failed = [r for r in results if r.status == FAIL]
    _report(results)
    if check and failed:
        print(f"CHECK FAILED: {len(failed)} case(s) failed", file=sys.stderr)
        return 1
    return 0


def _report(results: list[CaseResult]) -> None:
    passed = sum(r.status == PASS for r in results)
    failed = sum(r.status == FAIL for r in results)
    skipped = sum(r.status == SKIP for r in results)
    out = Path("docs/testing/document-toolchain/report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Document toolchain — real-input proof",
        "",
        "Generated by `scripts/document_toolchain.py`. Each case runs a document / "
        "spreadsheet / PDF / chart / OCR tool through the real `ToolPipeline.execute` on a "
        "real input and asserts the real output. No model, no container.",
        "",
        "## Summary",
        "",
        f"- Cases: **{len(results)}**",
        f"- pass: **{passed}**",
        f"- fail: **{failed}**",
        f"- skip (prereq absent): **{skipped}**",
        "",
        "| case | tool | status | detail |",
        "|---|---|---|---|",
    ]
    lines.extend(f"| {r.name} | `{r.tool}` | {r.status} | {r.detail} |" for r in results)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"document toolchain: {passed} pass / {failed} fail / {skipped} skip")
    print(f"report: {out}")


if __name__ == "__main__":
    raise SystemExit(run(check="--check" in sys.argv))

# Document toolchain — real-input proof

`scripts/document_toolchain.py` answers a question the tool matrix cannot: not "is the tool
callable?" but "does it do real document work correctly?" Each case feeds a **real input**
through the real `ToolPipeline.execute` path and asserts the **real output** — a created PDF
that pypdf reads back, a DuckDB sum that is right, a DOCX whose table round-trips, a chart
that is a valid PNG, and a scanned image that the tesseract binary genuinely reads.

These tools run **in-process** (pypdf, duckdb, the tesseract CLI, and hand-rolled DOCX/PDF/
XLSX/PPTX/PNG writers — no reportlab, openpyxl, python-docx or Pillow). **No model and no
sandbox container are involved**, so the proof is fast and deterministic and runs as a CI
guard (`tool-matrices` job).

## Run it

```bash
uv run python scripts/document_toolchain.py            # writes report.md
uv run python scripts/document_toolchain.py --check     # exit 1 if any case fails
```

Only the OCR case needs a host binary (`tesseract`); it reports `skip` if absent. CI installs
`tesseract-ocr` so the OCR case runs there too.

## Cases (2026-11-09): **14 pass / 0 fail**

| tool | what the case proves (real assertion) |
|---|---|
| `general.code` / `general.shell` | compute `6*7`; stdout is `42` |
| `general.write_file` / `read_file` | write three lines, read an offset/limit slice back |
| `general.query_table` | DuckDB `SELECT sum(amount)` over a real CSV → **35** |
| `general.inspect_table` | schema of the CSV lists the real columns |
| `general.pivot_table` | pivot region × product returns the product columns |
| `general.export_table` | export rows → a **valid XLSX** (OOXML zip) |
| `general.chart` | render a bar chart → a **valid PNG** (`\x89PNG`, non-trivial size) |
| `documents.create` (pdf) | create a PDF → **pypdf reads the planted canary back** |
| `documents.create` (docx) | create a DOCX → canary present in `word/document.xml` |
| `documents.create` (xlsx) | create an XLSX → valid workbook (`xl/workbook.xml`) |
| `documents.ingest` + `read` | ingest a created PDF → extracted text round-trips the canary |
| `documents.tables` | ingest a DOCX with a table → the cells round-trip |
| `documents.ocr` | **real tesseract** reads a committed scanned image (`CANARY` / `4821`) |

## Scope

This proves each document tool produces a **correct, real artifact** from a real input on the
in-process path. It is the complement to the tool matrix (callability) and the accuracy gym
(did the model *choose* the tool). It does not cover the LLM-backed document operations
(`documents.summarise`/`extract`/`compare`, `image.ask`) — those need a model and are proven
in the live agentic document suite. Table extraction from a text-layer PDF is not asserted
(pypdf recovers the text, not the cell grid); the DOCX path, which carries explicit table
markup, is used for the table case instead.

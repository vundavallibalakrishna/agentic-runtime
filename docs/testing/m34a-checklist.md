# M34a checklist

Proof date: 2026-11-05. No model call. No browser session. Labels say what actually ran.

`documents.create` builds DOCX, PDF and XLSX in the API process (OQ-71) and stores a workspace artifact. Download is the existing `GET /api/v1/files/{fileId}/content` path used by `general.export_table`. The chat card already links that URL when the tool result has `kind: file`.

## Fixture (ran in unit tests)

- [x] `documents.create` for `docx`, `pdf` and `xlsx` returns a non-empty file. A second render of the same payload matches the golden bytes in `libs/ar_domain/tests/fixtures/m34a/`
- [x] The DOCX opens as a zip with `word/document.xml`, styles and numbering. `extract_bytes` sees the Summary heading, the bullet, the table cells, and `R&D café`
- [x] The PDF starts with `%PDF-1.4`. pypdf reads the title and the summary. `extract_bytes` reads the same text
- [x] The XLSX opens as a zip with styles, a frozen header and shared strings. A numeric cell stays numeric. `general.inspect_table` reads the sheet from the run workspace
- [x] A title-and-sections payload with no sheets still produces a workbook. A sheets-only payload still produces a DOCX
- [x] The `brief` template omits the DOCX running header. `report` includes it
- [x] A missing format, a blank title, a non-list `sections`, and a table over 500 rows fail closed
- [x] The saved artifact is `kind=artifact` on the calling tenant. `../` in the file name stays under `/workspace/outputs`
- [x] Ingesting the created DOCX, then `documents.read` / `tables`, returns the heading and the table. Another tenant gets 404
- [x] Ingesting the created PDF and XLSX stores a ready library row
- [x] Fixture PPTX canary: two slides (`Roadmap`, `Risks`) round-trip through `extract_bytes`. This does not create a PPTX
- [x] `documents.create` is seeded at risk `W1` with `format` enum `docx`, `pdf`, `xlsx`

Command:

```bash
uv run pytest libs/ar_domain/tests/unit/test_m34a_create.py -q
```

## Not live

- [ ] Chat with a real model (Qwen or otherwise) that chooses `documents.create` and shows the download link
- [ ] Opening the golden files in Word, Excel, PowerPoint or a desktop PDF viewer
- [ ] Browser click-through of `/api/v1/files/{fileId}/content` while signed in
- [ ] A scanned-image or OCR path. M34a does not change OCR

Follow-up: one live chat that asks the assistant for the same Q3 brief as DOCX, PDF and XLSX, then downloads each file. A desktop open of those three files can sit beside that run. The PPTX reader canary can stay a fixture until a real deck is ingested in that same pass.

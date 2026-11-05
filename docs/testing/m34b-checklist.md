# M34b checklist

Proof date: 2026-11-05. No model call. No browser session. No desktop Office application. Labels say what actually ran.

Spreadsheet SQL runs in memory-only DuckDB 2.0.0 with `enable_external_access` false (OQ-60). `documents.fill_questionnaire` writes an xlsx with the `documents.create` workbook writer (OQ-86). `general.chart` can add a theme and a one-slide PPTX. Download stays `GET /api/v1/files/{fileId}/content`.

## Fixture (ran in unit tests)

- [x] `general.query_table` reports `engine: duckdb`. `ORDER BY stores DESC` on values 9 and 10 returns `B` first (text sort would return `A`)
- [x] `SUM(stores)` over that file is 19
- [x] `paths` loads two CSVs and a join returns `Austin`
- [x] `SELECT * FROM read_csv(...)` and `INSTALL httpfs` are `sql_rejected`. The sentinel value `LEAK` is not in the tool result. `SELECT read_csv('/etc/passwd')` is rejected by the guard
- [x] `general.pivot_table` sums `amount` by `region` and `product` (`N/pen` 10, `N/ink` 5, `S/pen` 2)
- [x] `documents.fill_questionnaire` writes `CAIQ-1` from a caller answer and leaves `CAIQ-2` blank with status `unanswered`
- [x] The same workbook grounded from a library passage contains `AES-256` on `CAIQ-1` and still leaves the cafeteria question blank
- [x] Another tenant's `documentId` returns `not_found` and the passage text is not in the error
- [x] `questionnaire-writeback` is published by `seed_composition` and names `documents.fill_questionnaire`
- [x] `documents.fill_questionnaire` is seeded at risk `W1`
- [x] Bar PNGs for `ink`, `forest` and `midnight` differ. An `area` PNG differs from `line`
- [x] `slide: true` stores `chart.png` and `chart.pptx`. The deck zip contains the PNG. `extract_bytes` reads the title and the narrative
- [x] An unknown theme is `validation_failed`
- [x] DOCX canary: `libs/ar_domain/tests/fixtures/m34a/q3-brief.docx` still yields `Summary` and `café` through `extract_bytes`
- [x] PPTX canary: the generated one-slide deck round-trips through `extract_bytes`. This does not open PowerPoint

Command:

```bash
uv run pytest libs/ar_domain/tests/unit/test_m34b_sheet_power.py libs/ar_domain/tests/unit/test_m23_tools.py libs/ar_domain/tests/unit/test_m34a_create.py -q
```

## Not live

- [ ] Chat with a real model that chooses `documents.fill_questionnaire`, `general.pivot_table` or `general.chart` with `slide`
- [ ] Opening the xlsx in Excel, the PPTX in PowerPoint, or the golden DOCX in Word
- [ ] Browser click-through of the file download while signed in
- [ ] A knowledge-base hybrid search inside the filler. The tool grounds from explicit answers, `sources`, or one library document. It does not call the embedding index
- [ ] DuckDB inside the general-tool sandbox. The engine is in the API process, with external access off

Follow-up: one live chat that fills the CAIQ fixture from an ingested policy, downloads the xlsx, and opens that file plus the chart slide in desktop Excel and PowerPoint.

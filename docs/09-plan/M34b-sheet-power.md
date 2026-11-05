# M34b — Sheet power

Depends on M34a. Spreadsheet SQL moves to in-process DuckDB. An agent can fill a questionnaire workbook and download the xlsx. Charts gain themes, an area kind, and a one-slide PPTX.

This milestone is one pull request. It does not change Temporal durability, connector live calls, or the browser tool.

## M34b-T01 DuckDB, questionnaire write-back, chart themes

**Spec:** [24-documents](../03-specs/24-documents.md), [OQ-60](../open-questions.md), [OQ-86](../open-questions.md).

**Do:**

- Run `general.query_table` and `general.export_table` SQL on memory-only DuckDB with external access disabled and the read-only SQL guard.
- Add `general.pivot_table` and accept `paths` so a query can join more than one workspace file.
- Add `documents.fill_questionnaire`. It fills a SIG/CAIQ-style xlsx from caller answers or a library document and writes an xlsx with the `documents.create` workbook writer.
- Seed the `questionnaire-writeback` skill with the demo composition.
- Extend `general.chart` with themes (`ink`, `slate`, `forest`, `ember`, `midnight`), kind `area`, and `slide` for a one-slide PPTX.
- Read the M34a DOCX fixture and the generated PPTX through the existing extractor.

**Done when:** unit tests cover a numeric order that SQLite text sort would get wrong, a join, a pivot, a rejected `read_csv`, questionnaire write-back including another tenant's document, two chart themes, and the slide text. The checklist states what was not opened in a desktop app or a live model.

**Tests:** `libs/ar_domain/tests/unit/test_m34b_sheet_power.py`. Checklist: [m34b-checklist](../testing/m34b-checklist.md).

## Out of scope

Temporal durability, connector credentials and live calls, browser automation, a desktop Word/Excel/PowerPoint pass, and a paid model choosing these tools.

# M34a — Office create

Depends on M24 and M32. An agent produces a DOCX, PDF or XLSX from a title, sections and tables. The file is a workspace artifact the chat can download. Reading DOCX and PPTX stays on the M24 extractor.

This milestone is one pull request. It does not change segregation of duties, fetch, search, OCR, vision, or the eval gym.

## M34a-T01 Create DOCX, PDF and XLSX

**Spec:** [24-documents](../03-specs/24-documents.md), [m24-documents](../06-security/m24-documents.md), [OQ-71](../open-questions.md).

**Do:**

- `documents.create` on `builtin://documents`. `format` is `docx`, `pdf` or `xlsx`.
- Accept a title, optional subtitle and author, sections (heading, paragraphs, bullets, one table) and sheets (name, columns, rows). Templates are `report`, `brief` and `sheet`.
- Write the file under the run workspace `outputs` directory and store it as an artifact. The chat card uses the same file id download as `general.export_table`.
- Keep the writers in `ar_domain.documents.create`. Do not add python-docx, openpyxl or reportlab to the API image.
- Round-trip the created DOCX, PDF and XLSX through the existing extractor. Add a fixture canary that reads a two-slide PPTX.

**Done when:** the three formats open in the unit tests, another tenant cannot read the ingested DOCX, and the checklist labels what was not run live.

**Tests:** `libs/ar_domain/tests/unit/test_m34a_create.py`. Checklist: [m34a-checklist](../testing/m34a-checklist.md).

## Out of scope

SoD policy changes, fetch and search providers, OCR and vision, the eval gym, and a PPTX create tool.

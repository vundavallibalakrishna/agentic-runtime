# M24 — Document intelligence

Depends on M23. A tenant uploads a file, or an agent finds one, and any agent can read it. The extraction is stored in Postgres. The text is untrusted data. A claim cites a passage or says the passage was not found.

This milestone is one pull request. Ingestion, tools and the library screens share one document row.

## M24-T01 Ingestion and storage

**Spec:** [24-documents](../03-specs/24-documents.md), [m24-documents](../06-security/m24-documents.md).

**Do:**

- Accept PDF, DOCX, XLSX, PPTX, TXT, MD, HTML and images.
- Extract text, headings, tables and page anchors. OCR a scanned page or an image when tesseract is installed.
- Revision `0026` stores the extraction. Dedupe by SHA-256. Cap size and pages. Encrypted, corrupt, unsupported and infected files are errors and are not stored.

**Done when:** the same file is stored once, another tenant receives 404, and a restart still lists the document.

**Tests:** `libs/ar_domain/tests/unit/test_m24_documents.py`.

## M24-T02 Agent tools

**Spec:** [24-documents](../03-specs/24-documents.md).

**Do:**

- `documents.list`, `search`, `ingest`, `read`, `outline`, `tables`, `summarise`, `compare`, `check`, `gaps`, `rewrite`, `redact`, `extract` on `builtin://documents`.
- Every claim cites an anchor from the document. A missing passage is reported as not found.
- Rewrite stores a diff. Nothing is saved until a person accepts it.
- Redaction returns the preview only.

**Done when:** a check against a requirement that is not in the file has no citation, and a rejected rewrite leaves the passage unchanged.

**Tests:** `test_m24_documents.py`, `services/api/tests/unit/test_m24_api.py`.

## M24-T03 Long documents

**Spec:** [24-documents](../03-specs/24-documents.md) §3.

**Do:**

- Chunk at about 1,000 characters with overlap. Keep the page and the heading.
- Retrieve at most 12,000 characters for a question.

**Done when:** a 300-page passage list is searched inside that budget in under two seconds.

**Tests:** `test_m24_documents.py`.

## M24-T04 Library screens

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- Library with upload, status and empty, loading and error states.
- Document view with anchors. Comparison. Check table. Rewrite review with accept and reject.
- Chat cards for the tool results.

**Done when:** Playwright captures light and dark at desktop and mobile, and the checklist records the Qwen3-32B run.

**Tests:** `apps/web/e2e/m24-documents.spec.ts`.

## Out of scope

Knowledge bases and memory (M25). Connector libraries, orchestration, and exposing agents. The GRC pack stays parked.

# Spec 24: Document library

A tenant uploads a file or an agent finds one. The platform extracts text, headings, tables and page anchors, stores that extraction in Postgres, and lets any agent read it. The bytes of the original upload stay on the process file store (OQ-59). The extraction is the durable document.

Document text is untrusted data. It is wrapped before it enters a model prompt. A claim cites an anchor that exists on the document. When no passage supports the claim, the result says so.

## 1. Files

Accepted types: PDF, DOCX, XLSX, PPTX, TXT, MD, HTML, and PNG, JPEG, GIF or WebP. The limit is 25 MB and 600 pages. The same SHA-256 in one tenant is stored once.

Errors:

| Code | When |
|---|---|
| `encrypted` | The PDF needs a password |
| `corrupt` | The file is empty or cannot be parsed |
| `unsupported` | The type is not in the list above |
| `too_many_pages` | More than 600 pages |
| `ocr_unavailable` | An image or a scanned page needs OCR and tesseract is not installed |
| `no_text` | Parsing succeeded and no text was found |
| infected | The upload scanner rejects the bytes. Nothing is stored |

## 2. Tools

Server `builtin://documents`. Tools: `list`, `search`, `ingest`, `read`, `outline`, `tables`, `summarise`, `compare`, `check`, `gaps`, `rewrite`, `redact`, `extract`, `create`.

`ingest` takes `fileId`, a workspace `path`, or a `url`. A URL uses the same egress rules as `general.fetch`.

`read` returns at most 12,000 characters. A longer file is searched and read by page or anchor.

`check` takes `requirements` or `standardDocumentId`. Each row is `met`, `partial` or `not_found`, with a citation and a confidence. `not_found` has no citation. When a model is configured, it judges the requirement from the retrieved passages (the whole document when it fits the retrieval budget), including a paraphrase, and the citation is the supporting sentence. A lexical overlap floor does not skip that call. Without a model, a requirement that shares too few words is `not_found`.

`rewrite` stores a proposal. Accepting a change updates the passage. Rejecting leaves it.

`redact` returns the redacted preview only.

`create` builds a new DOCX, PDF or XLSX. It does not read a library row. See §5.

## 3. Long documents

Passages are split at about 1,000 characters with a 120-character overlap. The page number and section heading stay on every piece. A question retrieves the pieces that share its words, up to 12,000 characters. A 300-page file is not copied into the prompt.

## 4. HTTP

`chat:use`. Paths are listed in the [API catalogue](../05-contracts/api-catalogue.md). Another tenant receives 404. `documents.create` is a tool, not a new HTTP route. Downloading the artifact uses the existing file content route.

## 5. Create

`documents.create` takes `format` (`docx`, `pdf` or `xlsx`), `title`, and optional `subtitle`, `author`, `template`, `fileName`, `sections` and `sheets`.

A section has `heading`, `level` (1 or 2), `paragraphs`, `bullets` and one optional `table` (`caption`, `columns`, `rows`). A sheet has `name`, `columns` and `rows`. A row is a list or an object keyed by the column names. JSON numbers stay numeric in a spreadsheet. Other values are text.

Templates are `report` (default for DOCX and PDF), `brief` (tighter, no running header) and `sheet` (default for XLSX). When a DOCX or PDF call has sheets and no sections, each sheet becomes a section table. When an XLSX call has sections and no sheets, each section table becomes a sheet and the prose becomes a Notes sheet.

The file is written to the run workspace at `outputs/<fileName>` and stored as an artifact. Chat downloads it with the same file content route as other workspace artifacts. The bytes are not a library document until something calls `ingest`. The tool result names the path and the size. It does not echo the body.

Limits: 40 sections, 12 sheets, 500 rows, 32 columns, 30 PDF pages, and the workspace file size cap. A bad payload is `validation_failed`. The writers are in-process and do not call a sandbox (OQ-71).

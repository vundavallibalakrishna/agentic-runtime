# Spec 24: Document library

A tenant uploads a file or an agent finds one. The platform stores the original bytes in the object store, keeps their sha256 and object key on the library row, and stores the extracted passages beside that key. Retrieval and citations point at those stored passages. The extraction is not a substitute for the original.

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
| `ocr_unavailable` | Tesseract ran and could not finish (for example it timed out) |
| `text_not_extracted` | An image or a scanned page had no reader, or the reader returned no text |
| `not_unicode` | A PDF's extracted text is not Unicode |
| `no_text` | Parsing succeeded and no text was found |
| infected | The upload scanner rejects the bytes. Nothing is stored |

## 2. Tools

Server `builtin://documents`. Tools: `list`, `search`, `ingest`, `read`, `outline`, `tables`, `summarise`, `compare`, `judge`, `missing`, `rewrite`, `redact`, `extract`, `create`, `ocr`.

`ocr` takes `fileId`, a workspace `path`, a `url`, or `documentId`. `engine` defaults to `tesseract`, which is proof `unit` (a local binary, not a model). `engine` `vision` uses the configured vision alias. That result is proof `live` only when the model answers, and the result names the model id and the date. Otherwise the result is `text_not_extracted` and the proof stays `unit`. `google_document_ai`, `aws_textract` and `azure_document_intelligence` return `not_live` and are not called. A PDF is Unicode text, or the tool returns `not_unicode` or `text_not_extracted`.

`image.ask` is server `builtin://image`, tool `ask`. It takes `fileId`, a workspace `path`, or a `url`, plus `question`. The image is PNG, JPEG, GIF or WebP, at most 8 MB. A PDF is refused; the caller uses `documents.ocr`. The call uses the agent `visionAlias` when it is set, otherwise the alias `vision`, through the same sealed provider key as chat. The key is not logged and is not returned. A fake alias, or a model that is not vision-capable, returns `vision_unavailable` and does not send the image. The image is untrusted data.

`ingest` takes `fileId`, a workspace `path`, or a `url`. A URL uses the same egress rules as `general.fetch`.

`read` returns at most 12,000 characters. A longer file is searched and read by page or anchor.

`judge` takes `ruleSetId`, `statements`, or an inline `ruleSet` (`id`, `version`, `items` of `itemId` and `statement`, `sourceFileId`, `sha256`). `missing` returns the rows that are not `supported`. A published rule-set version is immutable. `POST /api/v1/rule-sets` imports one and `GET /api/v1/rule-sets/{ruleSetId}` exports it. Another tenant receives 404.

A verdict is `supported` only when `quote` is a substring of the named stored passage. A quote that is not in that passage is `not_supported`. Lexical overlap is `not_judged` and is never a verdict. A model response that is not the schema is `failed`. Every row records the model id, the prompt hash, the rule-set id and the rule-set version. Library search uses the same stored-passage retrieval as a judgement.

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

## 6. Questionnaire fill

`documents.fill_questionnaire` reads one xlsx in the run workspace (`path`, optional `sheet`). It expects a question column and writes `Answer`, `Notes`, `Citation` and `Status` when those columns are missing. A caller `answers` entry matches on `id` or on the question text. Otherwise the tool scores the question against `sources` or against the passages of `documentId`. A score below the overlap floor leaves the answer blank and sets status `unanswered`. `searchLibrary` true also searches the caller's library. The tool does not call the knowledge embedding index.

The file is a new xlsx from the same writer as `documents.create`, plus a Trace sheet. Another tenant's `documentId` is `not_found`. The bytes are an artifact until something calls `ingest` (OQ-86).

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

Server `builtin://documents`. Tools: `list`, `search`, `ingest`, `read`, `outline`, `tables`, `diff`, `map`, `extract`, `edit`, `create`, `ocr`. The task tools (summarise, compare, judge, missing, crosscheck, rewrite, redact) were removed ([OQ-154](../open-questions.md)): the model plans those with the tools here. `edit` writes the new version twice from the same bytes: as a library document (`metadata.versionOf` names the original) and as a file under `/workspace/outputs` that the reply carries, so a person can download it from the conversation. The file is a Word document; a passage that is a heading keeps bold type and a larger size, and with `redline` each replaced passage is a tracked deletion and insertion. The same comparison `diff` makes is read by the Documents screen through `GET /api/v1/library-documents/{document_id}/diff?otherDocumentId=…` (permission `chat:use`): the sections that differ, each with both wordings and their anchors, and the counts of changed, added, removed and unchanged sections. It asks no model and stores nothing; a document the caller cannot see is 404.

`ocr` takes `fileId`, a workspace `path`, a `url`, or `documentId`. `engine` defaults to `tesseract`, which is proof `unit` (a local binary, not a model). `engine` `vision` uses the configured vision alias. That result is proof `live` only when the model answers, and the result names the model id and the date. Otherwise the result is `text_not_extracted` and the proof stays `unit`. `google_document_ai`, `aws_textract` and `azure_document_intelligence` return `not_live` and are not called. A PDF is Unicode text, or the tool returns `not_unicode` or `text_not_extracted`.

`image.ask` is server `builtin://image`, tool `ask`. It takes `fileId`, a workspace `path`, or a `url`, plus `question`. The image is PNG, JPEG, GIF or WebP, at most 8 MB. A PDF is refused; the caller uses `documents.ocr`. The call uses the agent `visionAlias` when it is set, otherwise the alias `vision`, through the same sealed provider key as chat. The key is not logged and is not returned. A fake alias, or a model that is not vision-capable, returns `vision_unavailable` and does not send the image. The image is untrusted data.

`ingest` takes `fileId`, a workspace `path`, or a `url`. A URL is read the way `general.fetch` reads one ([spec 08, "Reading public sites"](08-tool-registry-mcp.md)): the same egress rules, robots.txt, per-host limit and refusals, up to `AR_DOCUMENT_MAX_BYTES`. An address that answers with an error is not ingested.

**Copies of one address.** A document ingested from a URL has `source: connection` and `source_ref` set to the URL, and `metadata.fetched` holds what was measured when it was read (`status`, `etag`, `lastModified`, `contentType`, `bytes`, `sha256`, `fetchedAt`). A document is never overwritten, so reading the same URL again gives one of three results:

- **The content is new.** A new document is stored. If the caller can see an earlier copy of that URL, the result has `changed: true` and `previous` (the newest earlier copy), and the new document's `metadata.versionOf` is that copy's id. This is the link `documents.edit` already writes for an edited version.
- **The content is the same.** Nothing is stored. The result has `changed: false` and the existing document, whose `metadata.fetched` is brought up to date.
- **The site says it has not changed.** With `ifNoneMatch` or `ifModifiedSince` (the values from an earlier copy's `metadata.fetched`), a 304 stores nothing and returns `changed: false`.

`list` with `sourceRef` returns every copy of that URL the caller can see, newest first. Each copy stays readable with `read`, `outline` and `search`. Nothing here knows what the address is for.

**Diff.** `diff` takes `leftId` and `rightId` (two documents the caller can see: two copies of a URL, two versions of a file, or any two documents) and an optional `limit`. It pairs their sections by heading and then by shared wording (`documents.align`, with the floors `AR_DOCUMENT_ALIGN_LEXICAL` and `AR_DOCUMENT_ALIGN_COSINE`) and returns the sections that differ: `changed`, `added` or `removed`, each with its heading, anchors, pages and the stored text before and after, cut at `AR_DOCUMENT_DIFF_QUOTE_CHARS`. `counts` gives the number of each, and of sections that are the same; `total` is the number that differ, when `limit` cut the list. Text that differs only in white space is the same. No model is asked and nothing is judged: whether a change matters is for the caller. This is not the `compare` task tool that OQ-154 removed, which asked a model for a verdict ([OQ-171](../open-questions.md)).

`read` returns at most 12,000 characters. A longer file is searched and read by page or anchor.

`judge` takes `ruleSetId`, `statements`, or an inline `ruleSet` (`id`, `version`, `items` of `itemId` and `statement`, `sourceFileId`, `sha256`). `missing` returns the rows that are not `supported`. A published rule-set version is immutable. `POST /api/v1/rule-sets` imports one and `GET /api/v1/rule-sets/{ruleSetId}` exports it. Another tenant receives 404.

A verdict is `supported` only when `quote` is a substring of the named stored passage. A quote that is not in that passage is `not_supported`. Lexical overlap is `not_judged` and is never a verdict. A model response that is not the schema is `failed`. Every row records the model id, the prompt hash, the rule-set id and the rule-set version. Library search uses the same stored-passage retrieval as a judgement.

### 2.1 Cross-check

`crosscheck` takes `documentId` (a library document or an attached file) and an optional `focus`. It finds the places inside that one document that disagree with each other: the same thing given two values, a stated count or total that does not match what the document lists, or a summary or table line that contradicts the body. `compare` is for two documents and `judge` is for a list that comes from somewhere else.

Method:

1. Every stored passage of the document, and every stored table the passages do not hold, is sent to the model in one request. The document is read three times, because one reading misses what another finds, and a finding that stands in any reading is reported once. Each passage is wrapped as untrusted content and named by its anchor. `documentAnalysisRedaction` masks this text the same way it does for `judge`.
2. The model returns a JSON list of findings. A finding has a `statement`, a `kind` (`value_mismatch`, `count_mismatch`, `summary_mismatch` or `other`) and at least two `quotes`, each with an `anchor` and a `value`: the rating, figure, count, date or name that place gives.
3. A quote is kept only when it is in the stored passage that its anchor names. Spacing and capitals are ignored in that test. A masked quote is not in the stored passage, so it is discarded.
4. A finding is discarded when fewer than two quotes remain. A quote whose `value` is not a substring of that quote is dropped. The code does not fold quotes together, and it does not drop a finding because two quotes use the same words or the same number. That is the model's decision.
5. The text of the document is at most 40,000 characters. A longer document is refused with `validation_failed`, and the message gives the size and the limit. A part of a document is never checked in place of the whole.

The result has `findings`, `passagesRead` and `discarded` (the number of findings the model proposed that did not pass steps 3 and 4). With no finding, the tool says that no disagreement was found between the passages compared and how many passages were read. When the model does not answer, or its answer is not the schema, the tool returns `unavailable` and says that nothing was checked. It does not report an empty result.

Limits: the tool finds the disagreements that the model notices and can quote. It does not prove that a document agrees with itself. Steps 3 and 4 remove findings that have no evidence in the document. They do not add a finding the model missed. Nothing is stored: there is no row and no audit entry, as for `summarise`.

`rewrite` stores a proposal. Accepting a change updates the passage. Rejecting leaves it.

`redact` returns the redacted preview only.

`create` builds a new DOCX, PDF, PPTX or XLSX. It does not read a library row. See §5.

## 3. Long documents

Passages are split at about 1,000 characters with a 120-character overlap. The page number and section heading stay on every piece. A question retrieves the pieces that share its words, up to 12,000 characters. A 300-page file is not copied into the prompt.

## 4. HTTP

`chat:use`. Paths are listed in the [API catalogue](../05-contracts/api-catalogue.md). Another tenant receives 404. `documents.create` is a tool, not a new HTTP route. Downloading the artifact uses the existing file content route.

## 5. Create

`documents.create` takes `format` (`docx`, `pdf`, `pptx` or `xlsx`), `title`, and optional `subtitle`, `author`, `template`, `fileName`, `sections` and `sheets`.

A section has `heading`, `level` (1 or 2), `paragraphs`, `bullets` and one optional `table` (`caption`, `columns`, `rows`). A sheet has `name`, `columns` and `rows`. A row is a list or an object keyed by the column names. JSON numbers stay numeric in a spreadsheet. Other values are text.

Templates are `report` (default for DOCX, PDF and PPTX), `brief` (tighter, no running header) and `sheet` (default for XLSX). When a DOCX, PDF or PPTX call has sheets and no sections, each sheet becomes a section table. When an XLSX call has sections and no sheets, each section table becomes a sheet and the prose becomes a Notes sheet.

The file is written to the run workspace at `outputs/<fileName>` and stored as an artifact. Chat downloads it with the same file content route as other workspace artifacts. The bytes are not a library document until something calls `ingest`. The tool result names the path and the size. It does not echo the body.

A PPTX is a 16:9 deck. Slide 1 carries the title, the subtitle and the author. Each section then starts a slide with its heading as the slide title; the heading level is not shown. The layout uses fixed counts, not font measurement, so the same call always gives the same slides:

- Body text is 18 pt. A line holds 90 characters and a slide holds 14 lines. Paragraphs come first, then bullets. Text that does not fit moves to a next slide titled `<heading> (continued)`.
- A table is a native slide table in 14 pt with equal-width columns. A cell shows at most six lines and longer text ends with `...`. A one-line row is 0.35 in, so a slide holds sixteen of them, header included. A long table carries on over more slides and repeats its header.
- A section with text and a table puts both on one slide when both fit. Otherwise the text slides come first and the table follows on slides titled `<heading> (table)` and then `<heading> (table, continued)`.

The chart slide of `general.chart` is written by the same PPTX writer, so there is one presentation package layout in the product.

Limits: 40 sections, 12 sheets, 500 rows, 32 columns, 30 PDF pages, 60 slides, and the workspace file size cap. A bad payload is `validation_failed`. The writers are in-process and do not call a sandbox (OQ-71).

## 6. Questionnaire fill

`documents.fill_questionnaire` reads one xlsx in the run workspace (`path`, optional `sheet`). It expects a question column and writes `Answer`, `Notes`, `Citation` and `Status` when those columns are missing. A caller `answers` entry matches on `id` or on the question text. Otherwise the tool scores the question against `sources` or against the passages of `documentId`. A score below the overlap floor leaves the answer blank and sets status `unanswered`. `searchLibrary` true also searches the caller's library. The tool does not call the knowledge embedding index.

The file is a new xlsx from the same writer as `documents.create`, plus a Trace sheet. Another tenant's `documentId` is `not_found`. The bytes are an artifact until something calls `ingest` (OQ-86).

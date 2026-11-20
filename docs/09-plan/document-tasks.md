# Document tasks over stored and inline files

Status: revised (2026-11-20). The behaviour is [OQ-152](../open-questions.md).
Review, compare, gaps and compose are sample instructions. They are not
actions in core. The model plans in the existing tool loop and calls general
document tools. Measured facts (tokens, pages, outline size, table count, and
whether the text fits the registered context window) are given to the model.
Full text is inlined when it fits.

Date: 2026-11-20.

## 1. What a turn carries

A message may name `fileIds`, `collectionIds`, `items` and `taskTemplate`.
The instruction is the message text. There is no `strategy` field.

- `items` seed the conversation checklist when the plan is empty.
- `collectionIds` scope `documents.search` and the turn's auto-retrieve.
- `taskTemplate` loads a pack or agent template. Its schema is the turn's
  `responseFormat`. Sample templates live in `packs/examples/task-templates`.
- Planning uses `loop/planning.py`. It is on for a turn that has files,
  collections or the agent's default files, unless the agent sets
  `planning.enabled`.

`knowledge.fileIds` on the agent are readable by a user of that agent when
the file has an owner. A row with no owner is not granted.

## 2. Tools

The read-side tools are offered on any such turn, the same way `skills.load`
and `context.retrieve` are, and they sit in `_CORE_WHEN_SEARCHING`. Policy
still runs. Writes still need the documents binding.

| Tool | Contract |
|---|---|
| `documents.list` | `scope` is `turn`, `conversation` or `library`. Returns `documents`, `nextCursor`, `total`. |
| `documents.outline` | Heading level, page span and tokens. Cursor `o:N`. Page size is `AR_DOCUMENT_HEADING_CAP`. |
| `documents.read` | Cursor, heading, or anchor range. Limit is `AR_DOCUMENT_READ_CHARS`. |
| `documents.search` | `documentIds`, `fileIds`, `collectionIds`, `topK`. Returns `hits`, `nextCursor`, `total`. |
| `documents.tables` | Sheet or caption selection, row `offset` and `limit`. Real sheet names. PDF and PPTX tables are extracted. |
| `documents.map` | The caller's instruction, documents, an optional section filter, and an optional JSON Schema. Sections run on the existing `document_section` activity. Results are stored for `context.retrieve`. A missing model is an error. |
| `documents.extract` | One JSON Schema. A missing model is an error. |
| `image.ask` | `documentId` and `page` render that page. Offered only when a vision alias is configured. |
| `documents.create` | Renderers registered in `create/render.py`: docx, pdf, pptx, xlsx, md, html, csv. |
| `documents.edit` | Writes a new file version. `redline` produces a docx with tracked changes. The original passages are not changed. |

`documents.ingest` and `documents.ocr` stay.

## 3. Stores and formats

Migration `0056` copies library layout onto `documents` and makes
`collection_id` and `source_id` nullable. `library_documents` remains because
judgements and rule sets still reference it ([OQ-152](../open-questions.md)).

The library extractor is the layout parser. Knowledge `parse_bytes` calls it.
`.doc`, `.xls`, `.odt`, `.rtf` and `.msg` convert with LibreOffice in the
ingest image. `.eml` and `.zip` are read in process. A missing converter is
an error that names the tool.

A single file over `AR_DOCUMENT_MAX_PAGES` or `AR_DOCUMENT_MAX_BYTES` is
refused. Result sets page. They are not truncated without a cursor.

## 4. What core no longer does

Core does not choose a reading strategy, does not branch on task words, and
does not invent a summary, a rewrite or an extraction when the model does not
answer. The task-specific library routes and the fixed review table are gone.
A structured tool result is rendered from its own keys.

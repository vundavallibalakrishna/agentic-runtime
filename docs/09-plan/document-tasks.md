# Document tasks over stored and inline files

Status: revised (2026-11-20). The behaviour is the document decision in
[open questions](../open-questions.md) (the second OQ-154). The four gaps left
by the general-tools change are closed.
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

Migration `0057` copies library layout onto `documents` and makes
`collection_id` and `source_id` nullable. Migration `0058` moves judgements,
rule sets and the other library child rows onto `documents`, drops
`library_documents`, and adds SQL policies: a collection document stays
visible inside the tenant; a library extract is visible to its owner, or to a
user of a published agent whose default files name it when that file has an
owner. A row with no owner and no collection is not visible. Content-hash
dedupe stays on `documents`.

Docling is the layout parser for PDF, Office and HTML on every ingest path.
`documents/extract.py` reads a format Docling cannot, and it is what a process
without Docling uses. The ingest image installs Docling. When a Temporal
client is connected, the API stages the bytes and the ingest worker parses
them, for a library upload, a collection upload and a reprocess alike. A collection
upload up to `AR_INGEST_INLINE_MAX_BYTES` travels with the request; a larger
one is read by the worker from the file store. When Docling should have read
a file and did not, the fallback's text is kept and the document's metadata
says so: `parser` is `fallback` and `parserNote` gives the reason
(`layout_parser_failed:<error type>`, `layout_parser_not_installed` or
`layout_parser_read_nothing`). A failure is also logged as
`layout_parser_failed` with the error type, the kind of file and its size,
and nothing from the file. The service image holds the templates of
`packs/examples/task-templates`, so `taskTemplate` works on an install that
mounts no pack folder. `.doc`, `.xls`, `.odt`, `.rtf` and `.msg` convert with LibreOffice in
the ingest image. `.eml` and `.zip` are read in process. A missing converter
is an error that names the tool.

A single file over `AR_DOCUMENT_MAX_PAGES` or `AR_DOCUMENT_MAX_BYTES` is
refused. Result sets page. They are not truncated without a cursor.

## 4. What core no longer does

Core does not choose a reading strategy, does not branch on task words, and
does not invent a summary, a rewrite or an extraction when the model does not
answer. A missing model is an error. Judgement and cross-check ask the model
for one JSON object and keep a quote only when it is in the stored passage.
The task-specific library routes and the fixed review table are gone.
A structured tool result is rendered from its own keys. Create limits are
`AR_DOCUMENT_CREATE_MAX_*`.

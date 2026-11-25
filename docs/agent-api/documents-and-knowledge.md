# Documents and knowledge bases

All of these use a service-account key on `/api/v1`. Replace `{{BASE_URL}}`.

## Upload a file

```bash
curl -s {{BASE_URL}}/api/v1/files:upload \
  -H "Authorization: Bearer $CURA_KEY" \
  -F "upload=@policy.pdf" -F "mime_type=application/pdf"
```

Form fields: `upload` (the file), `mime_type`, `expires_after_seconds`,
`replaces_file_id`. These four are snake_case; JSON bodies are camelCase. The reply:
`id`, `name`, `mimeType`, `sizeBytes`, `status`, and `documentId` once the file has been
read into the library. `415` means the type is not accepted and `413` that it is too
large; `GET /api/v1/files:limits` says what is.

Needs `chat:use`.

## The document library

Every readable upload becomes a library document: its text split into passages, each
with an anchor such as `p1-s0`.

| Call | What it gives |
|---|---|
| `POST /api/v1/library-documents` (form field `upload`) | upload straight into the library |
| `GET /api/v1/library-documents` | the documents you can see |
| `GET /api/v1/library-documents/{id}` | one document, with its outline |
| `GET /api/v1/library-documents/{id}/passages?pageFrom=&pageTo=` | its text, passage by passage |
| `GET /api/v1/library-documents/{id}/diff?otherDocumentId=` | what changed between two documents |
| `DELETE /api/v1/library-documents/{id}` | remove it |

## Save documents to a knowledge base

A knowledge base is a collection. An agent that lists the collection answers from it and
cites it. The workspace needs an embedding model first.

**Create a collection** (`knowledge:manage`):

```bash
curl -s {{BASE_URL}}/api/v1/knowledge/collections \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"slug":"policies","name":"Policies","visibility":"tenant"}'
```

**Add files you uploaded.** Up to 100 at a time; each must be ready and uploaded by the
same account:

```bash
curl -s {{BASE_URL}}/api/v1/knowledge/collections/$COLLECTION_ID/documents \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"fileIds":["'$FILE_ID'"]}'
```

**Add one document another way**, with `POST .../collections/$COLLECTION_ID/members`:

| `kind` | Send | Adds |
|---|---|---|
| `library` | `libraryDocumentId` | a document already in the library |
| `url` | `url`, `title` (optional) | the page at that address |
| `text` | `text`, `title`, `externalId` (optional) | text you send |

The reply says `indexed` or `unchanged`. Sending the same text again changes nothing;
`"force": true` indexes it again.

**Keep a page in step.** Add a web source and let it sync on a schedule:

```bash
curl -s {{BASE_URL}}/api/v1/knowledge/collections/$COLLECTION_ID/sources \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"name":"Website","kind":"web","config":{"url":"https://example.com/pricing"},"syncSchedule":"0 3 * * *"}'

curl -s {{BASE_URL}}/api/v1/knowledge/sources/$SOURCE_ID:sync \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"mode":"incremental"}'
```

The sync answers `202` with a `jobId`. `GET /api/v1/knowledge/jobs/$JOB_ID` gives its
`status` and `stats` (`added`, `updated`, `unchanged`, `deleted`, `failed`).

**Search** (`knowledge:read`):

```bash
curl -s {{BASE_URL}}/api/v1/knowledge/search \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"query":"notice period","collectionIds":["'$COLLECTION_ID'"],"topK":5}'
```

Each hit has `title`, `uri`, `snippet`, `score`, `pageFrom`, `pageTo`, `documentId` and
`collectionId`.

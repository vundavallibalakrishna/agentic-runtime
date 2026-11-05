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

Server `builtin://documents`. Tools: `list`, `search`, `ingest`, `read`, `outline`, `tables`, `summarise`, `compare`, `check`, `gaps`, `rewrite`, `redact`, `extract`.

`ingest` takes `fileId`, a workspace `path`, or a `url`. A URL uses the same egress rules as `general.fetch`.

`read` returns at most 12,000 characters. A longer file is searched and read by page or anchor.

`check` takes `requirements` or `standardDocumentId`. Each row is `met`, `partial` or `not_found`, with a citation and a confidence. `not_found` has no citation. When a model is configured, it judges the requirement from the retrieved passages (the whole document when it fits the retrieval budget), including a paraphrase, and the citation is the supporting sentence. A lexical overlap floor does not skip that call. Without a model, a requirement that shares too few words is `not_found`.

`rewrite` stores a proposal. Accepting a change updates the passage. Rejecting leaves it.

`redact` returns the redacted preview only.

## 3. Long documents

Passages are split at about 1,000 characters with a 120-character overlap. The page number and section heading stay on every piece. A question retrieves the pieces that share its words, up to 12,000 characters. A 300-page file is not copied into the prompt.

## 4. HTTP

`chat:use`. Paths are listed in the [API catalogue](../05-contracts/api-catalogue.md). Another tenant receives 404.

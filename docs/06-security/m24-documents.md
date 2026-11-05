# M24 documents

## Untrusted content

Extracted text, tables and tool results are data. `docs.summarise`, `check`, `gaps`, `rewrite` and `extract` wrap the passages with `ar_common.wrapping.wrap_untrusted` before a model sees them. The tool pipeline also wraps the tool result and runs the injection check because `builtin://documents` is treated as open-world content. A model answer that cites an anchor which is not in the retrieved passages is dropped. The citation is the sentence that contains the model's quote, not the first sentence of a weakly related passage. When a model is configured, a paraphrase is judged from those passages and `not_found` means the model found no supporting quote. Without a model, a requirement with no overlapping passage is `not_found` and has no citation.

## Uploads

The library rejects files over 25 MB and over 600 pages. `POST /api/v1/library-documents` may be that large. Other request bodies stay at 1 MB. `scan_bytes` runs before extraction. An infected file is audited as `library_document.rejected` and is not stored. Encrypted, corrupt and unsupported files are not stored.

## OCR

Images and PDF pages with almost no text layer are sent to the `tesseract` binary when it is on `PATH`. The process gets a scrubbed environment and a temporary file that is deleted afterwards. There is no network. A runtime without tesseract returns `ocr_unavailable` (OQ-61). `documents.ocr` is that path as a tool. The canary fixture in `docs/testing/fixtures/m33b/` must yield `M33B CANARY` and `CODE 4821`. A trailing all-caps line is kept, so the second line is not dropped as an empty heading. Google Document AI, Amazon Textract and Azure Document Intelligence are not called. Those engine names return `not_live` and the tesseract install path (OQ-70). Office and PDF parsing stays in the API process: the general sandbox does not ship those parsers, and the byte and page caps bound the work.

`image.ask` sends the image to the vision alias. The provider key is the sealed chat key and is placed only on the outbound `Authorization` header. It is stripped from the model text before the tool result is stored. A model whose capabilities do not include `vision`, and whose name is not a known vision model, is not called. The default seeded `vision` alias is fake-llm, so the tool returns `vision_unavailable` until an operator points that alias at a vision model. The image is untrusted. Instructions inside it are not followed. A chart answer keeps dates and numbers the way document analysis does, so a code such as `4821` is not masked as a date.

## Redaction

`documents.redact` and the redact endpoint return the masked string and entity counts. The original text is not a field of the response. Email and phone patterns always run. Presidio runs when the `pii` extra is installed, through `ar_domain.pii.analyzer.redact` with the outbound profile.

Check, compare, summarise, rewrite and the library read tools use the analysis profile unless `features.documentAnalysisRedaction` is true or the agent sets `safety.piiMasking`. That profile keeps dates, locations and control ids (`90 days`, `Ireland`, `P6.3`). Chat tool results and outbound previews still use the full mask (`features.piiRedaction`, default true). See [OQ-69](../open-questions.md).

## Storage

Revision `0026` stores the extraction: title, hash, passages, tables, checks, comparisons and rewrites. Rows are tenant scoped with RLS. The original upload bytes are not in these tables. A restart that hydrates the tenant still lists the document and its passages. The hash is unique per tenant so the same file is not stored twice.

## What was tested

Unit tests cover encrypted, corrupt, unsupported and oversized files, a scanner rejection, dedupe, a cross-tenant 404, a missing-evidence check, a citation that is a real passage, a rewrite that does not change the document until it is accepted, a redaction preview that does not contain the original email, and retrieval of one page out of 300 inside a 12,000 character budget. The HTTP test repeats the cross-tenant 404. The checklist records the Qwen3-32B run on public documents.

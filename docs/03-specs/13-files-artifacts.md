# Spec 13: Files and artifacts (`ar_domain.files`)

Endpoints served by `api`; processing (scan, MIME sniffing, previews) by `ingest-worker` (`FileProcessWorkflow`, queue `ar-ingest`); storage in S3-compatible object storage (SeaweedFS by default, any S3 API). Owns `files` ([schema §11](../04-data/schema.md#11-files-ar_domainfiles)). Decision: [ADR-0014](../02-architecture/adr/ADR-0014-object-storage.md). PRD: [04-chat](../01-prd/04-chat.md) (attachments, artifacts), [06-sandboxes](../01-prd/06-sandboxes.md).

## 1. Responsibilities

1. Uploads (presigned PUT for large files, direct multipart ≤ 25 MiB), downloads (presigned GET or proxied), previews.
2. Malware scanning, MIME verification, size/type policy, quarantine.
3. Artifacts created by agents (sandbox exports, screenshots, offloaded tool results) with lineage (`run_id`, `conversation_id`).
4. Access control derived from ownership and the owning object (conversation, knowledge document, skill, eval dataset).
5. Retention and deletion (including DPDP erasure).

## 2. Storage layout

- Bucket `AR_S3_BUCKET` (default `ar-files`); dedicated tiers use `ar-t-{tenant_slug}`.
- Object key `t/{tenant_id}/{kind}/{yyyy}/{mm}/{file_id}` (never contains user-supplied names).
- Server-side encryption: `AR_S3_SSE` (`AES256` default where supported; otherwise volume encryption is required, see [helm-k8s](../07-ops/helm-k8s.md)).
- Bucket policy: private; no public ACLs; presigned URLs expire in 300 s (`AR_S3_PRESIGN_TTL_S`), are generated against `AR_S3_PUBLIC_ENDPOINT` (browser-reachable) and include `Content-Disposition: attachment; filename*=UTF-8''<name>`.

## 3. Access rules (`files.service.can_read(principal, file)`)

| kind | Readable by |
|---|---|
| `upload` | owner; viewers of `conversation_id` if attached to a message |
| `artifact`, `tool_result` | viewers of `conversation_id`; the run's user; routine owner for routine runs |
| `sandbox_snapshot` | system only |
| `knowledge_raw`, `knowledge_parsed` | users who can read the document (ACL), managers of the collection |
| `skill_asset` | users who can see the skill |
| `avatar` | any tenant user |
| `export` | owner only |
| `openapi_spec` | tool server owners/reviewers |
| `eval_dataset` | `evals:manage` |
| `event_payload` | routine owner |

## 4. Public API

#### POST /api/v1/files
`chat:use` (uploads) or the permission of the purpose. Body `{name (≤ 255), mime_type, size_bytes, sha256?, purpose: "upload"|"avatar"|"openapi_spec"|"eval_dataset"|"skill_asset", conversation_id?}`. Checks: `size_bytes ≤ tenant.settings.security.max_upload_mb`, MIME in `allowed_upload_mime_types` (default: PDF, Office, OpenDocument, text/*, CSV, JSON, Markdown, PNG, JPEG, GIF, WebP, ZIP), plan storage quota. Creates `files` row (`status='pending_upload'`) and returns `{file: File, upload: {url, method: "PUT", headers: {"Content-Type", "x-amz-checksum-sha256"?}, expires_at}}`.

#### POST /api/v1/files/{file_id}:complete
Owner. Verifies the object exists (`HEAD`), size matches, checksum matches (if provided); starts `FileProcessWorkflow`; returns `File` with `status='pending_upload'` → becomes `ready` (or `quarantined`) asynchronously; the client polls `GET /api/v1/files/{file_id}` or listens to the notifications stream. For files ≤ 5 MiB processing is awaited inline up to 10 s so chat attachments are usually `ready` in the response.

#### POST /api/v1/files:upload
Multipart form (`file`, `purpose`, `conversation_id?`), ≤ 25 MiB; equivalent to create + upload + complete. Used by the web app for small files and by API clients.

#### GET /api/v1/files
Caller's files. Query `kind` (`upload|artifact|export`), `conversation_id`, `q` (name ILIKE), `mime_prefix`. Item `File {id, name, mime_type, size_bytes, kind, status, scan_status, conversation_id, run_id, preview: {page_count?, width?, height?, text_excerpt?, thumbnail_url?}, created_at}`.

#### GET /api/v1/files/{file_id}
#### GET /api/v1/files/{file_id}/content
`302` to a presigned GET URL, or streams through `api` when `AR_FILES_PROXY_DOWNLOADS=true` (air-gapped installs where object storage is not browser-reachable). `status` must be `ready`. Query `inline=true` allowed only for images and PDFs (`Content-Type` preserved, `Content-Security-Policy: sandbox` header on proxied responses). Audit `file.downloaded` for classification ≥ `confidential`.

#### GET /api/v1/files/{file_id}/thumbnail
PNG thumbnail (≤ 512 px) for images/PDF first page/Office (via the preview pipeline); 404 if none.

#### DELETE /api/v1/files/{file_id}
Owner (or admins for tenant cleanup). Soft delete (`deleted_at`, `status='deleted'`), object deleted by `RetentionSweepWorkflow` after 24 h (undo window not exposed in v1). Files referenced by knowledge documents are deleted only via the knowledge API.

## 5. `FileProcessWorkflow(file_id)` (`ingest-worker`, id `file-{file_id}`)

1. `sniff_mime` (`filetype` on the first 8 KiB): mismatch with declared type in a dangerous direction (e.g. declared `text/plain`, actual executable) → `quarantined`.
2. `scan` with ClamAV (`clamd` over TCP, `AR_CLAMAV_ADDRESS`; `AR_FILES_SCANNER=clamav|none`); infected → `scan_status='infected'`, `status='quarantined'`, audit `file.quarantined`, notification to the owner. Scanner unavailable → retry 5× then `scan_status='error'` and `status='quarantined'` for uploads (fail closed), `ready` for agent artifacts (they originate in the sandbox) with `scan_status='skipped'`.
3. `preview`: images (Pillow: dimensions, thumbnail), PDF (`pypdf` page count + first-page render via `pdftoppm`), Office (LibreOffice headless convert first page in the ingest image), text excerpt (first 1,000 chars). Stored in `files.preview` and a thumbnail object.
4. `status='ready'`; emit outbox `file.ready`.

## 6. Artifacts

- Created by `mcp-gateway` (tool results with images/large output, `sandbox.export_file`, `/workspace/outputs/` auto-export, `browser.screenshot`) via `files.service.create_artifact(run, name, mime, stream)`; owner = run user; `conversation_id`, `run_id` set; `artifact.created` event emitted by the runtime/gateway; referenced from assistant messages as `file` parts.
- Artifact names are sanitised (`[^\w.\- ]` → `_`, ≤ 120 chars) and de-duplicated within a conversation (`report (2).pdf`).
- Viewer support in the web app: images, PDF, CSV/XLSX (table preview from first 1,000 rows), Markdown, code/text (syntax highlighted), HTML (rendered **only** as source text), charts (PNG/SVG as image with SVG served as attachment).

## 7. Retention

`retention_until` = `created_at + tenant.settings.retention.files_days` for uploads/artifacts (NULL for `knowledge_*`, `skill_asset`, `avatar`, managed by their owners); `tool_result` 30 days; `export` 7 days; `sandbox_snapshot` = template `retention_days`; legal hold on the conversation suspends deletion. `RetentionSweepWorkflow` ([spec 17](17-audit-usage-metering.md)) deletes objects and rows.

## 8. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AR_S3_ENDPOINT` | `http://localhost:8333` | Internal endpoint |
| `AR_S3_PUBLIC_ENDPOINT` | `http://localhost:8333` | Browser-reachable endpoint for presigned URLs |
| `AR_S3_REGION` | `us-east-1` | |
| `AR_S3_ACCESS_KEY_ID` / `AR_S3_SECRET_ACCESS_KEY` | (secret) | |
| `AR_S3_BUCKET` | `ar-files` | |
| `AR_S3_SSE` | `AES256` | `none` to disable |
| `AR_S3_PRESIGN_TTL_S` | `300` | |
| `AR_FILES_PROXY_DOWNLOADS` | `false` | |
| `AR_FILES_SCANNER` | `clamav` (prod) / `none` (dev) | |
| `AR_CLAMAV_ADDRESS` | `clamav:3310` | |

## 9. Metrics

`ar_files_uploaded_total{purpose}`, `ar_files_bytes_total{kind}`, `ar_file_scan_total{result}`, `ar_file_process_seconds`, `ar_storage_bytes{tenant}` (rollup gauge).

## 10. Test plan

- Unit: access table, name sanitisation, retention computation.
- Integration (SeaweedFS + ClamAV containers): presigned upload → complete → ready; EICAR test file → quarantined; size/MIME rejections; download redirect with attachment disposition; proxied download mode; cross-tenant access → 404; artifact creation from a sandbox export.

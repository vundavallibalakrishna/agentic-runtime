# PRD 03 — Knowledge

Knowledge managers build collections from company sources; agents retrieve with hybrid search that respects source permissions and cite what they use. Spec: [spec 10](../03-specs/10-knowledge.md), [definition-schema §5](../05-contracts/definition-schema.md#5-knowledgecollection-kind-knowledgecollection), [ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md). Plan: [M7](../09-plan/M07-knowledge.md).

### US-KN-01 · Create a collection (P0)
As a **knowledge manager**, I want to create a collection with visibility and ACL mode so that I control who can bind and read it.
- `POST /api/v1/knowledge/collections` with `visibility` (`private`, `team`, `tenant`), `acl_mode` (`source` or `collection`), classification and chunking/embedding settings (defaults from spec 10).
- Only creator, owner-team leads or `knowledge:manage` holders can manage it; others with visibility can bind it to agents.
- Spec: spec 10 §2–3. Plan: M7-T01, M7-T08.

### US-KN-02 · Upload documents (P0)
As a **knowledge manager**, I want to upload files (PDF, Office, HTML, Markdown, text, images with OCR) so that they become searchable.
- Upload → `ingestion_jobs` progress visible; document reaches `indexed` (or `failed` with a reason) — parse (Docling/LibreOffice/OCR), chunk, embed, index (default: Postgres + pgvector with full-text search; optional Qdrant backend) with tenant, collection and ACL filters.
- Files above `AR_INGEST_MAX_BYTES` are rejected with 413; malware-flagged files are quarantined.
- Spec: spec 10 §4.2, [spec 13](../03-specs/13-files-artifacts.md). Plan: M7-T03.

### US-KN-03 · Sync from company sources (P0 for `web`, `s3`, `upload`; P1 for others)
As a **knowledge manager**, I want to connect sources (web, S3, SharePoint, Confluence, Google Drive, database, MCP resources) so that collections stay current.
- `POST /api/v1/knowledge/collections/{collection_id}/sources` with kind-specific config and credential; `:test` validates access; schedules incremental syncs using each source's change detection; `:sync`, `:pause`, `:resume` available.
- Deleted upstream documents are removed from the index on the next sync.
- Spec: spec 10 §4.1, §5. Plan: M7-T04, M7-T05, M7-T06.

### US-KN-04 · Respect source permissions (P0)
As a **security officer**, I want users to retrieve only documents they may read in the source system.
- With `acl_mode='source'`, document principals are synced (`AclSyncWorkflow`) and mapped to platform users/groups; retrieval filters `acl ∩ principals(user) ≠ ∅` and `classification ≤ user clearance`, always with `tenant_id` and bound/visible collections.
- An ACL change upstream is effective after the next ACL sync (`acl_sync_schedule`, e.g. every 10 minutes); unmapped principals grant nothing.
- Mandatory isolation tests prove a user without access cannot retrieve a document through chat, search API or subagents.
- Spec: spec 10 §2, §5.3. Plan: M7-T02, M7-T05.

### US-KN-05 · Grounded answers with citations (P0)
As a **member**, I want answers grounded in company documents with clickable citations.
- Agents with bound collections use `knowledge.search` (and optional `auto_retrieve`); retrieved text is wrapped as untrusted data; the answer carries citation markers rendered as chips that open the source snippet and link.
- When nothing relevant is found the agent says so rather than inventing ([eval-strategy §3](../08-quality/eval-strategy.md#3-metrics) unanswerable accuracy).
- Spec: spec 10 §3 `POST /api/v1/knowledge/search`, [spec 07](../03-specs/07-agent-runtime.md). Plan: M7-T07, M7-T08.

### US-KN-06 · Search a collection directly (P1)
As a **member**, I want to search collections I can read without starting a chat.
- `POST /api/v1/knowledge/search` with query, collections, filters, `top_k`; results show title, snippet, source link, score; same ACL rules as agents.
- Spec: spec 10 §3. Plan: M7-T02, M7-T08.

### US-KN-07 · Operate collections (P0)
As a **knowledge manager**, I want to see sync status, failures and re-index when settings change.
- Jobs list with status and per-document errors; `:reingest` a document; `:reindex` a collection after changing chunking/embedding (old index serves until the new one is complete); deleting a document removes it from the index and storage.
- Spec: spec 10 §3, §4.4–4.5. Plan: M7-T06.

### US-KN-08 · Knowledge from files in a conversation (P0)
As a **member**, I want to attach files to a chat and ask about them without creating a collection.
- Attached files are processed (`FileProcessWorkflow`) and readable by the agent only within that conversation (`files.list`/`files.read`), never by other users.
- Spec: [spec 13](../03-specs/13-files-artifacts.md), spec 08 §9. Plan: M2-T07, M4-T05.

# Spec 10: Knowledge (`ar_domain.knowledge`, `ingest-worker`)

Endpoints served by `api`; ingestion runs on `ingest-worker` (`services/ingest`, package `ar_ingest`, queue `ar-ingest`); retrieval (`knowledge.search`) runs in-process in `mcp-gateway` and `runtime-worker` via `ar_domain.knowledge.retrieval`. Owns `knowledge_collections`, `knowledge_sources`, `documents`, `document_chunks`, `chunk_embeddings`, `ingestion_jobs` ([schema §8](../04-data/schema.md#8-knowledge-ar_domainknowledge)). Vector and lexical indexing goes through the `RetrievalStore` port (§6): the default `pgvector` adapter keeps everything in Postgres (§7); the optional `qdrant` adapter keeps vectors in Qdrant (§8). Decision: [ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md). PRD: [03-knowledge](../01-prd/03-knowledge.md).

## 1. Responsibilities

1. Collections and sources (upload, web, S3, SharePoint, Confluence, Google Drive, database, MCP resources) with schedules.
2. Ingestion: fetch → parse → chunk → (contextualise) → embed → index through the `RetrievalStore` port; incremental via cursors and `version_hash`; deletions.
3. ACL capture and sync (document-level principals) and enforcement **inside** the vector query.
4. Hybrid retrieval with rerank, answerability threshold, citations; late verification for `sensitivity='high'`.
5. Re-indexing (blue/green by `index_version`) when chunking or embedding model changes, and migration between retrieval backends (§9).

## 2. Access model

- Collection visibility (`private|team|tenant`) controls who can **see and bind** a collection. Managing a collection: creator, owner team leads, or `knowledge:manage`.
- Document access is decided per user by principals: `principals(user) = ["user:{id}", "tenant:*"] + ["group:{gid}" for each group] + ["team:{tid}" for each team]`.
- `acl_mode='source'`: `documents.acl_principals` come from the source system, mapped to platform principals (§5.3). `acl_mode='collection'`: principals derived from collection visibility (`tenant:*`, `team:{owner_team_id}`, or `user:{created_by}`).
- Retrieval always filters `tenant_id`, `collection_id ∈ bound & visible collections`, and `acl ∩ principals ≠ ∅`, plus `classification ≤ user clearance`.

## 3. Public API

#### GET /api/v1/knowledge/collections
`knowledge:read`. Visible collections. Item `KnowledgeCollection {id, slug, name, description, visibility, acl_mode, sensitivity, classification, embedding_alias, index_version, owner_team, stats: {documents, chunks, bytes, failed}, sources_count, last_sync_at, can_manage}`.

#### POST /api/v1/knowledge/collections
`knowledge:manage` (or team-scoped). Body `{slug, name, description?, visibility?, owner_team_id?, acl_mode?, sensitivity?, classification?, embedding_alias?, chunking?: {target_tokens: 128..2048, overlap_pct: 0..30, contextual: bool}}`. Creates the collection and an `upload` source named `uploads`. Optional `text_search_config: "simple"|"english"` (default `simple`, §7.3). Resolves `embedding_model_id` and its dimension (must be supported by the backend, §7.1, else `422 validation_failed` with detail `unsupported_embedding_dims`), sets `store_backend` from `AR_VECTOR_BACKEND` and calls `RetrievalStore.ensure_collection` to obtain `store_collection` (§6).

#### GET /api/v1/knowledge/collections/{collection_id}
#### PATCH /api/v1/knowledge/collections/{collection_id}
`{name?, description?, visibility?, owner_team_id?, sensitivity?, classification?}`. Changing `chunking` or `embedding_alias` is done via `:reindex`.
#### DELETE /api/v1/knowledge/collections/{collection_id}
409 if bound by a published agent version. Otherwise starts deletion (`DeleteDocumentWorkflow` per document in batches, then `RetrievalStore.drop_collection`) and returns `202`.

#### POST /api/v1/knowledge/collections/{collection_id}:reindex
Body `{embedding_alias?, chunking?, text_search_config?}`. Starts `ReindexCollectionWorkflow` (§4.5). Response `202 {job_id}`.

#### GET /api/v1/knowledge/collections/{collection_id}/sources
#### POST /api/v1/knowledge/collections/{collection_id}/sources
Body `{name, kind, config: KnowledgeSourceConfig, secret_id?, data_connection_id?, sync_schedule?, acl_sync_schedule?}` ([definition-schema §5](../05-contracts/definition-schema.md#5-knowledgecollection-kind-knowledgecollection)). Creates Temporal Schedules `ks-sync-{source_id}` and `ks-acl-{source_id}` (overlap policy SKIP, timezone = tenant default). Triggers an initial full sync.

#### GET /api/v1/knowledge/sources/{source_id}
#### PATCH /api/v1/knowledge/sources/{source_id}
Updates config/schedules (schedules updated in Temporal).
#### DELETE /api/v1/knowledge/sources/{source_id}
Deletes schedules, then documents of the source (async, `202`).

#### POST /api/v1/knowledge/sources/{source_id}:test
Runs the connector's `check()` (credentials, reachability, sample listing of ≤ 5 items) → `{ok, sample: [{external_id, title}], error?}`.

#### POST /api/v1/knowledge/sources/{source_id}:sync
Body `{mode: "incremental"|"full"}`. Starts `SourceSyncWorkflow` (if one is running, returns its job). Response `202 {job_id}`.

#### POST /api/v1/knowledge/sources/{source_id}:pause
#### POST /api/v1/knowledge/sources/{source_id}:resume
Pause/unpause the Temporal schedules; `status`.

#### GET /api/v1/knowledge/collections/{collection_id}/documents
Query `q` (title trigram), `status`, `source_id`. Item `Document {id, title, uri, mime_type, size_bytes, status, error, source: {id, name, kind}, classification, acl_principal_count, source_modified_at, indexed_at}`. Only documents the caller can read are listed (managers see all with `can_read` flags).

#### POST /api/v1/knowledge/collections/{collection_id}/documents
Add uploaded files: body `{file_ids: [uuid] (≤ 100), acl_principals?: [..] (default per acl_mode)}`. Files must be `ready` and owned by the caller. Creates documents in the `uploads` source and starts `IngestDocumentWorkflow` for each. Response `202 {documents: [Document]}`.

#### GET /api/v1/knowledge/documents/{document_id}
Includes `summary`, `language`, `heading outline`, ingestion history (jobs touching it).

#### GET /api/v1/knowledge/documents/{document_id}/chunks
Managers only (debugging). Items `{id, ordinal, text, context_prefix, heading_path, page_from, page_to, token_count}`.

#### POST /api/v1/knowledge/documents/{document_id}:reingest
#### DELETE /api/v1/knowledge/documents/{document_id}
Uploads only (source-synced documents are deleted at the source); starts `DeleteDocumentWorkflow`.

#### GET /api/v1/knowledge/collections/{collection_id}/jobs
#### GET /api/v1/knowledge/jobs/{job_id}
`IngestionJob {id, kind, status, stats, error, triggered_by, started_at, finished_at, failures: [{document_id|external_id, error}] (≤ 100)}`.
#### POST /api/v1/knowledge/jobs/{job_id}:cancel

#### POST /api/v1/knowledge/search
`knowledge:read`. Retrieval playground as the caller. Body `{query, collection_ids: [uuid] (≥ 1), top_k?: ≤ 20, debug?: bool}` → `{hits: [Hit], answerable: bool, debug?: {backend, dense: [...], lexical: [...], fused: [...], store_ms, rerank_ms, total_ms}}`. `Hit {document_id, chunk_id, collection_id, title, uri, snippet, score, rerank_score, page_from, page_to, heading_path}`.

## 4. Ingestion workflows (`ingest-worker`)

### 4.1 `SourceSyncWorkflow(source_id, mode, job_id)` id `sync-{source_id}`
1. `start_job` (ingestion_jobs `running`).
2. Loop `list_changes(source_id, cursor, page_size=200)` (activity, heartbeat each page) → `ChangePage {items: [SourceItem{external_id, title, uri, mime_type, modified_at, version_hint, acl?: [ExternalPrincipal]}], deleted_external_ids, next_cursor, done}`.
3. For each item: `upsert_document_stub` (new or `version_hint` changed or `full`) → start child `IngestDocumentWorkflow` (max 16 concurrent children per sync; `AR_INGEST_SYNC_CONCURRENCY`). Unchanged → count.
4. Deletions: listed deletions → `DeleteDocumentWorkflow`; `full` mode: documents not seen → delete.
5. Save `cursor` after each page (resumable). `finish_job` with stats; `status='partially_failed'` if any child failed. `continue_as_new` every 50 pages.

### 4.2 `IngestDocumentWorkflow(document_id)` id `ingest-{document_id}`
Activities (each idempotent; retries 5×, 2 s→2 min, non-retryable `unsupported_format`, `too_large`, `access_denied`):
1. `fetch_raw` → stream to S3 `files(kind='knowledge_raw')`, compute `version_hash`; if equal to the indexed version → finish `unchanged`.
2. `parse` (Docling: PDF incl. OCR for scanned pages, DOCX, PPTX, XLSX (sheets → Markdown tables, ≤ 50k cells), HTML (boilerplate removal), MD, TXT, CSV, EML/MSG, images via OCR) → Markdown with page anchors → `files(kind='knowledge_parsed')`. Max raw size 200 MiB (`AR_INGEST_MAX_BYTES`), max pages 2,000.
3. `chunk`: heading-aware recursive splitter on Markdown; target `chunking.target_tokens` (tokenizer: `tiktoken` `o200k_base` approximation), overlap %, never split tables/code blocks below 1.5× target; records `heading_path`, page range.
4. `contextualise` (if `chunking.contextual`): document summary (fast alias, ≤ 200 words) + per-chunk context prefix ≤ 80 tokens (fast alias, batched 8 chunks/call; purpose `ingest_context`). Summary is always generated (used by `knowledge.get_document` and list views).
5. `embed`: dense via `model-gateway` `/v1/embeddings` (`embedding_alias`, batches of 64, text = `context_prefix + "\n" + heading_path + "\n" + text`); the lexical signal is derived by the adapter from the same text (pgvector: generated `tsvector`; qdrant: BM25 sparse vector).
6. `index`: in one database transaction insert `document_chunks` and call `RetrievalStore.upsert` with `IndexedChunk`s (§6.2) into the collection's `store_collection` at the current `index_version` (the pgvector adapter joins the transaction; the qdrant adapter writes right after commit, idempotently by chunk id, and the activity retries until both succeed); then `RetrievalStore.delete` the document's entries with `index_version_ne` = current and delete those `document_chunks`; set `status='indexed'`, `indexed_at`; update collection stats (debounced).
7. PII classification (optional, tenant feature `pii_redaction`): Presidio scan of parsed text; if PII density above threshold and collection classification < `confidential`, set document `classification='confidential'` and emit audit `document.classified`.

### 4.3 `AclSyncWorkflow(source_id)` id `acl-{source_id}`
Connector `list_acl_changes(cursor)` → per document new external principal set → map (§5.3) → if `acl_hash` changed: update `documents.acl_principals` and call `RetrievalStore.set_acl` for the document (pgvector: same transaction). Target freshness ≤ 10 min (schedule `*/10 * * * *` default). Group membership changes need no document update (resolved at query time).

### 4.4 `DeleteDocumentWorkflow(document_id)` id `del-doc-{document_id}`
`RetrievalStore.delete` by `document_id`, delete chunks, mark document `deleted`, delete raw/parsed files (S3), audit.

### 4.5 `ReindexCollectionWorkflow(collection_id, new_settings)` id `reindex-{collection_id}`
Signature `ReindexCollectionWorkflow(collection_id, new_settings, target_backend: str | None = None)`. Blue/green: `ensure_collection` for the target (new `index_version`; new `store_collection` when dims or backend change), re-chunk/re-embed all documents (from parsed files, no refetch) with concurrency 8 — or, when only `target_backend` is given, copy vectors (§9) — then in one transaction switch `knowledge_collections.index_version`/`store_backend`/`store_collection`/`embedding_model_id`/`text_search_config`, then delete the old version's entries (after `AR_VECTOR_MIGRATION_RETAIN_HOURS` when the backend changed). Retrieval during reindex uses the old index.

## 5. Connectors (`ar_ingest.connectors`)

### 5.1 Interface (`ar_connector_sdk.DocumentSource`, see [connector-sdk](../05-contracts/connector-sdk.md))
`check()`, `list_changes(cursor, page_size)`, `fetch(external_id) -> bytes + mime`, `list_acl_changes(cursor)`, `check_access(external_id, user: UserIdentity) -> bool` (for late verification; optional).

### 5.2 Built-in connectors
| kind | Change detection | ACL source |
|---|---|---|
| `upload` | n/a (API) | from request or collection |
| `web` | crawl with ETag/Last-Modified; robots.txt; egress proxy + allowlist; same-domain links; `max_pages`, `max_depth` | collection |
| `s3` | `ListObjectsV2` + ETag | collection |
| `sharepoint` | Microsoft Graph delta queries per drive | Graph permissions (users by email/UPN, groups by Entra group id) |
| `confluence` | CQL `lastmodified > cursor` | space permissions + page restrictions (users by email, groups by name) |
| `google_drive` | Drive changes API (`startPageToken`) | Drive permissions (users/groups by email; `domain` → `tenant:*`; `anyone` → `tenant:*`) |
| `database` | `updated_at > watermark` via `mcp-sql`-equivalent guarded query (same read-only DSN rules) | optional `acl` column (array of emails/group names) |
| `mcp_resource` | `resources/list` + resource version/etag via `mcp-gateway` | collection |

### 5.3 Principal mapping
External principals `{type: user|group|domain|anyone, id?, email?, name?}` → `user:{users.id}` by email match (case-insensitive), `group:{groups.id}` by `groups.external_id` then `groups.name`, `domain`/`anyone` (same company domain verified in `tenant_domains`) → `tenant:*`. Unmapped principals are dropped and counted (`stats.unmapped_principals`); a document left with no principals is readable by nobody except via `collection` override (never defaults to public).

## 6. Retrieval store port (`RetrievalStore`)

Module `ar_domain.knowledge.store`. Domain code (`retrieval.py`, ingestion activities, workflows) depends only on this port; adapters live in `ar_domain.knowledge.store_pgvector` and `ar_domain.knowledge.store_qdrant` and are selected by `get_retrieval_store(backend: Literal["pgvector","qdrant"])`. The `qdrant-client` and `fastembed` dependencies are an optional extra (`ar-domain[qdrant]`) imported only by the qdrant adapter; the import-linter contract `retrieval-adapters` and the architecture test forbid importing `store_pgvector`/`store_qdrant` anywhere except the factory in `store.py` ([coding-standards-python](../08-quality/coding-standards-python.md)).

### 6.1 Interface

```python
class RetrievalStore(Protocol):
    backend: ClassVar[Literal["pgvector", "qdrant"]]
    capabilities: ClassVar[StoreCapabilities]
    # StoreCapabilities = {native_sparse: bool, transactional_with_pg: bool, supported_dims: frozenset[int]}

    async def ensure_collection(self, spec: PhysicalCollectionSpec) -> str: ...
        # idempotent; returns the store_collection name; raises UnsupportedDims
    async def drop_collection(self, store_collection: str, tenant_id: UUID, collection_id: UUID) -> None: ...
    async def upsert(self, store_collection: str, chunks: Sequence[IndexedChunk],
                     *, session: AsyncSession | None = None) -> int: ...
        # idempotent by chunk_id; batches of at most 512
    async def delete(self, store_collection: str, f: DeleteFilter,
                     *, session: AsyncSession | None = None) -> int: ...
    async def set_acl(self, store_collection: str, tenant_id: UUID, document_id: UUID,
                      acl: Sequence[str], classification: str,
                      *, session: AsyncSession | None = None) -> int: ...
    async def search(self, q: HybridQuery) -> list[ScoredChunk]: ...
    async def count(self, store_collection: str, tenant_id: UUID, collection_id: UUID,
                    index_version: int) -> int: ...
    def export(self, store_collection: str, tenant_id: UUID, collection_id: UUID,
               index_version: int, batch_size: int = 512) -> AsyncIterator[list[ExportedVector]]: ...
        # ordered by chunk_id
    async def health(self) -> StoreHealth: ...
```

### 6.2 Types (`ar_domain.knowledge.store_types`, Pydantic v2, frozen)

| Type | Fields |
|---|---|
| `PhysicalCollectionSpec` | `tenant_id, collection_id, isolation_tier, model_key, dims` |
| `IndexedChunk` | `chunk_id, tenant_id, collection_id, document_id, source_id, index_version, dense: list[float]` (len = dims), `lexical_text: str` (the embedding text of §4.2 step 5), `text_search_config`, `acl: list[str]`, `classification, mime_type, title, language, modified_at` |
| `DeleteFilter` | `tenant_id` (required) and at least one of `collection_id`, `document_id`, `index_version`, `index_version_ne`, `chunk_ids` |
| `SearchTarget` | `collection_id, index_version, store_collection, text_search_config` |
| `HybridQuery` | `tenant_id, text, dense: list[float], targets: list[SearchTarget]` (1..20, same dims), `principals: list[str]` (non-empty), `allowed_classifications: list[str]` (non-empty), `dense_k=50, lexical_k=50, fused_k=50, rrf_k=60` |
| `ScoredChunk` | `chunk_id, document_id, collection_id, score` (RRF), `dense_rank: int \| None, lexical_rank: int \| None` |
| `ExportedVector` | `chunk_id, document_id, index_version, dense: list[float]` |
| `StoreHealth` | `backend, ok, latency_ms, detail` |

### 6.3 Contract rules (all adapters)

1. Every read and write is scoped by `tenant_id`; `search` with empty `principals` or `allowed_classifications` raises `ValueError` (never "no filter").
2. A chunk is returned only if `tenant_id` matches, `(collection_id, index_version)` is one of `targets`, `acl ∩ principals ≠ ∅`, and `classification ∈ allowed_classifications`. Filters apply **inside** the candidate query, never as a post-filter that could return fewer than `dense_k` candidates while more matching chunks exist.
3. Fusion is Reciprocal Rank Fusion: `score = Σ 1/(rrf_k + rank)` over the dense and lexical lists (rank starts at 1); ties broken by `chunk_id` ascending; results ordered by `score` descending, length ≤ `fused_k`.
4. `upsert` and `delete` are idempotent; `set_acl` is visible to the next `search` (read-your-writes).
5. Errors map to `StoreUnavailable` (retryable) and `StoreError` (non-retryable); `knowledge.search` turns `StoreUnavailable` into tool error `retrieval_unavailable`.
6. Adapters emit spans `ar.retrieval.{operation}` with attributes `ar.retrieval.backend`, `ar.retrieval.targets`, `ar.retrieval.candidates`.

### 6.4 Retrieval pipeline (`ar_domain.knowledge.retrieval`, backend-independent)

1. Resolve targets: bound and visible collections with their current `index_version`, `store_backend`, `store_collection`, `text_search_config`; group by backend (two groups exist only during a migration).
2. Principals of the acting user (§2; group count capped per [spec 02](02-identity-tenancy.md)) and allowed classifications from clearance.
3. Embed the query once per distinct embedding model of the targets (targets are also grouped by dims).
4. `RetrievalStore.search` per (backend, dims) group; merge groups by RRF score.
5. Rerank via `model-gateway` `/v1/rerank` (`rerank` alias) on the top `AR_KNOWLEDGE_RERANK_CANDIDATES` (text = title + heading path + chunk text loaded from `document_chunks`) → `rerank_score` (normalised 0..1 with sigmoid when the engine returns logits); keep ≥ `min_score`, take `top_k`. Rerank unavailable → fall back to RRF order with a `warning`.
6. **Late verification** (`sensitivity='high'`): for the final hits, call connector `check_access` per document (cached `ar:acl:{doc}:{user}` 5 min); deny → drop. Timeout 2 s → drop (fail closed).
7. Answerability: `answerable = any hit ≥ min_score`. If false, the tool returns `"No sufficiently relevant documents were found."` and no citations.

## 7. pgvector adapter (default)

### 7.1 Storage

- Table `chunk_embeddings` ([schema §8](../04-data/schema.md#8-knowledge-ar_domainknowledge)): one row per chunk (the chunk row already carries its `index_version`), with denormalised filter columns (`tenant_id, collection_id, document_id, source_id, index_version, acl, classification`), `dims`, `embedding halfvec` (no fixed dimension) and `tsv tsvector` generated from `lexical_text` with the row's `text_search_config`. Standard tenant RLS policy ([rls](../04-data/rls.md)).
- Supported dimensions: **384, 768, 1024, 1536, 3072**. Revision `0014_knowledge` ([migrations §3](../04-data/migrations.md#3-initial-revision-plan)) creates one partial HNSW index per dimension: `CREATE INDEX ix_chunk_emb_hnsw_{d} ON chunk_embeddings USING hnsw ((embedding::halfvec({d})) halfvec_cosine_ops) WITH (m = 16, ef_construction = 64) WHERE dims = {d}`. A model with another dimension is rejected at collection creation (`422 validation_failed`, detail `unsupported_embedding_dims`).
- `store_collection` for this adapter is `pg:{dims}` (all isolation tiers; a `dedicated_db` tenant's rows live in its own database through `AR_TENANT_DB_ROUTES`). `ensure_collection` only validates `dims`; `drop_collection` deletes rows by `collection_id`.
- Lexical index `CREATE INDEX ix_chunk_emb_tsv ON chunk_embeddings USING gin (tsv)`; filter indexes: btree `(tenant_id, collection_id, index_version)`, GIN `(acl)`, btree `(document_id)`.

### 7.2 Writes

`upsert` = `INSERT … ON CONFLICT (chunk_id) DO UPDATE` in batches of 512, using the caller's session (same transaction as `document_chunks`) when given. `set_acl` = `UPDATE chunk_embeddings SET acl = :acl, classification = :c WHERE tenant_id = :t AND document_id = :d`. `delete` = `DELETE … WHERE tenant_id = :t AND <selector>`.

### 7.3 Hybrid query (one SQL statement per `search`)

Runs on `AR_VECTOR_PG_READ_DSN` when set (read replica; RLS session variables set identically), else on the primary. Inside the transaction: `SET LOCAL hnsw.ef_search = <AR_VECTOR_PG_EF_SEARCH>` (default 100), `SET LOCAL hnsw.iterative_scan = relaxed_order`, `SET LOCAL hnsw.max_scan_tuples = 20000`.

```sql
WITH targets(collection_id, index_version) AS (
  SELECT * FROM unnest(:collection_ids::uuid[], :index_versions::int[])
), dense AS (
  SELECT chunk_id, row_number() OVER () AS rank FROM (
    SELECT ce.chunk_id FROM chunk_embeddings ce JOIN targets t USING (collection_id, index_version)
    WHERE ce.dims = 1024 AND ce.tenant_id = :tenant_id
      AND ce.acl && :principals::text[] AND ce.classification = ANY(:allowed::text[])
    ORDER BY ce.embedding::halfvec(1024) <=> :q::halfvec(1024)
    LIMIT :dense_k) d
), lexical AS (
  SELECT chunk_id, row_number() OVER (ORDER BY score DESC, chunk_id) AS rank FROM (
    SELECT ce.chunk_id, ts_rank_cd(ce.tsv, qq.query, 32) AS score
    FROM chunk_embeddings ce JOIN targets t USING (collection_id, index_version),
         (SELECT websearch_to_tsquery('simple', :text) AS query) qq
    WHERE ce.tsv @@ qq.query AND ce.tenant_id = :tenant_id
      AND ce.acl && :principals::text[] AND ce.classification = ANY(:allowed::text[])
    ORDER BY score DESC, ce.chunk_id LIMIT :lexical_k) l
)
SELECT ce.chunk_id, ce.document_id, ce.collection_id,
       COALESCE(1.0 / (:rrf_k + d.rank), 0) + COALESCE(1.0 / (:rrf_k + l.rank), 0) AS score,
       d.rank AS dense_rank, l.rank AS lexical_rank
FROM dense d FULL JOIN lexical l USING (chunk_id) JOIN chunk_embeddings ce USING (chunk_id)
ORDER BY score DESC, ce.chunk_id
LIMIT :fused_k;
```

- The example shows dims 1024. The dims literal is interpolated from the supported-dims allowlist (never from input) so the planner matches the partial index; every other value is a bound parameter.
- The tsquery is `websearch_to_tsquery(cfg, :text)` OR-combined (`||`) over the distinct `text_search_config`s of the targets. Allowed configs: `simple` (default; language-neutral, suits mixed Indian-language corpora) and `english`.
- `ts_rank_cd(…, 32)` (cover density, normalised `rank/(rank+1)`) is the BM25-style lexical score; only its rank order enters RRF.
- The builder is `store_pgvector.build_hybrid_sql()`; unit tests assert the tenant, ACL and classification predicates are present in both branches and the dims literal comes from the allowlist.

### 7.4 Operations

`health()` = `SELECT extversion FROM pg_extension WHERE extname = 'vector'` (must be ≥ 0.8.0) with a 2 s timeout. Index build parameters and `maintenance_work_mem` for large reindexes: [scaling §4](../07-ops/scaling.md#4-retrieval-store-sizing).

## 8. Qdrant adapter (optional)

Used when `AR_VECTOR_BACKEND=qdrant` (new collections) or when any collection has `store_backend='qdrant'`; requires `AR_QDRANT_URL` (plus `AR_QDRANT_API_KEY` when the server enforces one) and the `ar-domain[qdrant]` extra (installed in the default images; unused unless configured).

- Physical collections (`store_collection`): shared tier `ar_kn_{model_key}_{dims}` (e.g. `ar_kn_bge_m3_1024`) with Qdrant multitenancy (payload index `tenant_id` `keyword` with `is_tenant=true`, HNSW `payload_m=16`, `m=0`). Dedicated tiers (`isolation_tier != 'shared'`): `ar_kn_t_{tenant_short}_{model_key}_{dims}`. `ensure_collection` creates the collection and payload indexes if missing.
- Named vectors: `dense` (size = dims, Cosine, on-disk for large tenants, scalar int8 quantisation) and sparse `bm25` (modifier IDF) computed from `lexical_text` with `fastembed` model `Qdrant/bm25` (cache `AR_FASTEMBED_CACHE_DIR`, pre-baked in the image for air-gapped installs).
- Point id = `chunk_id`. Payload: `tenant_id`, `collection_id`, `document_id`, `source_id`, `index_version`, `acl` (keyword[]), `classification`, `mime_type`, `title`, `modified_at`, `language`; payload indexes on all filterable keys.
- `search`: one Query API request with two `prefetch` branches (dense top `dense_k`, sparse top `lexical_k`), both with filter `{must: [tenant_id, should-of-pairs (collection_id, index_version), acl any ∈ principals (lists > 500 split into `should` blocks of 500), classification ∈ allowed]}`; the adapter computes RRF itself (§6.3 rule 3) so scores and tie-breaks match the pgvector adapter.
- `set_acl` = `set_payload {acl, classification}` by filter `document_id`; `delete` = delete points by filter; `export` = scroll with vectors ordered by id.
- Writes are not transactional with Postgres: ingestion commits `document_chunks` first, then upserts; a crash between the two is healed by the activity retry (idempotent upsert). `RetrievalStoreAuditWorkflow` (queue `ar-ingest`, Temporal Schedule `retrieval-store-audit`, `0 3 * * *`, only registered when a qdrant collection exists) compares `count()` with `document_chunks` per collection and re-upserts missing chunks.
- `health()` = `GET {AR_QDRANT_URL}/readyz`.

## 9. Migrating between backends

Operator-only (platform admin in SaaS, installation admin in single-tenant). Command `python -m ar_ingest.cli migrate-store --to {pgvector|qdrant} [--tenant <slug>] [--collection <id>] [--dry-run]` (run with `uv run` locally or `kubectl exec deploy/ingest-worker --` in a cluster; module `services/ingest/src/ar_ingest/cli.py`, connects to Temporal with the worker's settings) starts `MigrateRetrievalStoreWorkflow(target_backend, tenant_id?, collection_id?)` (queue `ar-ingest`, id `migrate-store-{target}-{scope}`):

1. Set `AR_VECTOR_BACKEND` to the target first, so new collections are created there.
2. Preconditions: target adapter `health().ok`; target supports the dims of every collection in scope (otherwise the collection is reported as skipped).
3. For each collection with `store_backend != target` (max 4 concurrently) run child `ReindexCollectionWorkflow(collection_id, new_settings={}, target_backend=target)`:
   1. `ensure_collection` on the target; new `index_version = current + 1`.
   2. Copy: `source.export(...)` batches → join `document_chunks`/`documents` for `lexical_text`, ACL, classification and metadata → `target.upsert(...)` at the new `index_version` (no re-embedding). Afterwards a catch-up pass re-indexes documents with `indexed_at` later than the copy start.
   3. Verify: `target.count == source.count` and a **parity check**: 20 sampled chunk texts used as queries with the collection's full principal set; average overlap of the source and target top-10 must be ≥ 70 % (lexical scoring differs between engines). Failure → job `failed`, no switch.
   4. Switch in one transaction: `store_backend`, `store_collection`, `index_version`; audit `collection.store_migrated` (actor = operator, details `{from, to, index_version}`).
   5. After `AR_VECTOR_MIGRATION_RETAIN_HOURS` (default 24) delete the old entries from the source. Within that window `python -m ar_ingest.cli migrate-store --rollback --collection <id>` switches back without copying.

Embedding model changes are not migrations: they use `:reindex` with a new `embedding_alias` (re-embed).

## 10. `RetrievalStore` conformance suite

Location `libs/ar_domain/tests/conformance/retrieval_store/`; every test is parametrised by the fixture `retrieval_store` (`ar_testing.fixtures.retrieval_store`, params `pgvector` and `qdrant`, each on testcontainers). Marker `conformance`. Every adapter must pass every case; a new adapter is mergeable only when the suite passes in CI.

| # | Case |
|---|---|
| C01 | `ensure_collection` is idempotent and returns the same `store_collection`; unsupported dims → `UnsupportedDims` |
| C02 | `upsert` twice with the same chunk ids → `count` unchanged; changed fields overwrite |
| C03 | Tenant isolation: identical chunks in tenants A and B; searches as A return only A's chunks, also with a forged target naming B's collection |
| C04 | ACL leak test: 3 users × 30 documents with disjoint and overlapping ACLs, 50 random queries each: zero chunks outside the user's principals |
| C05 | Classification filter excludes chunks outside the allowed set |
| C06 | Only the listed `index_version` per collection is returned (blue/green) |
| C07 | Lexical recall: a query containing a rare exact token (`ZX-4471`) returns the chunk containing it in the top 3 even when that chunk's dense vector is random |
| C08 | Dense recall: with `fake-llm` deterministic embeddings, a query in the same embedding cluster and with no shared tokens returns the target chunk in the top 3 |
| C09 | RRF: scores equal `Σ 1/(rrf_k+rank)`; ties broken by `chunk_id`; length ≤ `fused_k` |
| C10 | Filter inside the query: 10,000 chunks of which the user can read 25 scattered ones; `search` with `dense_k=10` returns 10 readable chunks |
| C11 | `set_acl` revocation is visible to the next search |
| C12 | `delete` by `document_id`, `index_version_ne` and `collection_id`; a `DeleteFilter` without a selector is rejected |
| C13 | `search` with empty principals or classifications raises `ValueError` |
| C14 | `export` returns every chunk exactly once ordered by `chunk_id`; export → upsert into a second collection preserves search results |
| C15 | `health` ok on a running store; with the store stopped, operations raise `StoreUnavailable` within 5 s |
| C16 | 1,000 chunks upsert in ≤ 10 s on CI hardware |

CI: the `pgvector` parametrisation runs in `python-integration` on every PR; the `qdrant` parametrisation runs in job `conformance-qdrant` on PRs touching `libs/ar_domain/src/ar_domain/knowledge/store*` and nightly ([ci-cd](../07-ops/ci-cd.md)).

## 11. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AR_VECTOR_BACKEND` | `pgvector` | `pgvector` \| `qdrant`: backend for new collections and target of migrations |
| `AR_VECTOR_PG_READ_DSN` | (unset) | Optional read-replica DSN for pgvector searches |
| `AR_VECTOR_PG_EF_SEARCH` | `100` | `hnsw.ef_search` for pgvector searches |
| `AR_VECTOR_MIGRATION_RETAIN_HOURS` | `24` | Keep source entries after a backend switch (rollback window) |
| `AR_QDRANT_URL` | (unset) | Qdrant URL; required only when the qdrant adapter is used |
| `AR_QDRANT_API_KEY` | (secret, unset) | Qdrant API key |
| `AR_INGEST_SYNC_CONCURRENCY` | `16` | Child workflows per sync |
| `AR_INGEST_MAX_BYTES` | `209715200` | Max raw document size |
| `AR_INGEST_ACTIVITY_CONCURRENCY` | `32` | Per worker |
| `AR_FASTEMBED_CACHE_DIR` | `/var/cache/fastembed` | BM25 model cache for the qdrant adapter (pre-baked in image for air-gapped) |
| `AR_KNOWLEDGE_RERANK_CANDIDATES` | `50` | Candidates sent to rerank |
| `AR_EGRESS_PROXY_URL` | `http://squid:3128` | Web crawler egress |

Readiness: `api`, `ingest-worker`, `runtime-worker` and `mcp-gateway` report not ready when `AR_VECTOR_BACKEND=qdrant` without `AR_QDRANT_URL`, or when any collection uses a backend whose adapter is not configured.

## 12. Limits

Per plan: `max_knowledge_documents` (default 100k), `max_knowledge_bytes` (default 50 GiB). Per collection: sources ≤ 20. Query `top_k` ≤ 20. Upload batch ≤ 100 files.

## 13. Metrics

`ar_ingest_documents_total{kind,result}`, `ar_ingest_stage_seconds{stage}`, `ar_ingest_queue_depth` (Temporal task queue backlog), `ar_knowledge_search_seconds{stage}`, `ar_knowledge_search_hits`, `ar_knowledge_unanswerable_total`, `ar_acl_sync_lag_seconds{source}`, `ar_late_verification_denied_total`, `ar_retrieval_store_seconds{backend,operation}`, `ar_retrieval_store_errors_total{backend,operation,kind}`, `ar_retrieval_store_count_drift{collection}` (qdrant audit).

## 14. Test plan

- Unit: chunker (tables/code not split, overlap, page ranges), principal mapping, pgvector SQL builder and Qdrant filter builder (tenant, ACL, classification present), RRF merge across groups, rerank fallback, answerability threshold.
- Conformance: §10 for every adapter.
- Integration (testcontainers Postgres+pgvector, `fake-llm` embeddings with deterministic hashing vectors): upload → indexed → searchable; **mandatory ACL leak test** through the API (two users, three docs with different ACLs, 50 random queries; zero leaks); ACL change propagates within one `AclSyncWorkflow` run; reindex switch is atomic; delete removes `chunk_embeddings` rows. Job `conformance-qdrant` additionally runs a pgvector → qdrant → pgvector migration round trip that must pass the parity check.
- Retrieval quality eval (M13): golden Q/A set per sample collection (`evals/knowledge/*.yaml`): recall@8 ≥ 0.85, MRR ≥ 0.6 against the reference models, gated on the pgvector adapter (reported, not gated, for qdrant).

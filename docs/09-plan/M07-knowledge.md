# M7 — Knowledge

Goal: grounded answers. Knowledge managers create collections fed by uploads and connectors; the ingest pipeline parses, chunks, contextualises, embeds and indexes documents through the `RetrievalStore` port (default adapter: Postgres + pgvector with full-text hybrid search) with ACL principals; agents retrieve with hybrid search + rerank filtered by the acting user's principals and cite sources.

Exit criteria: two users with different SharePoint permissions (stubbed Graph API) ask the same question; each gets answers citing only documents they can access; deleting a document at the source removes it from answers after the next sync; retrieval leak test and the `RetrievalStore` conformance suite pass for the pgvector adapter. The optional Qdrant adapter and backend migration (M7-T09, M7-T10) are not part of the M7 exit criteria; they must be done before M15-T07 (release).

---

### M7-T01 · Revision 0014 `knowledge` and collections/sources/documents API
- **Depends on:** M4-T04, M2-T07
- **Areas:** `ar_domain/knowledge/**`, migration 0014, `ar_api/routers/knowledge.py`
- **Spec:** [spec 10 §2–3](../03-specs/10-knowledge.md#3-public-api), [schema §8](../04-data/schema.md#8-knowledge-ar_domainknowledge)
- **Do:** Tables of schema §8; access model (collection visibility, managers, readers; document ACLs); endpoints `GET/POST /api/v1/knowledge/collections`, `GET/PATCH/DELETE /api/v1/knowledge/collections/{collection_id}`, `GET/POST /api/v1/knowledge/collections/{collection_id}/sources`, `GET/PATCH/DELETE /api/v1/knowledge/sources/{source_id}`, `GET/POST /api/v1/knowledge/collections/{collection_id}/documents` (upload by file id), `GET/DELETE /api/v1/knowledge/documents/{document_id}`, `GET /api/v1/knowledge/documents/{document_id}/chunks`, `GET /api/v1/knowledge/collections/{collection_id}/jobs`, `GET /api/v1/knowledge/jobs/{job_id}`; resolver `knowledge_collection`; plan limits `max_collections`, `max_knowledge_documents`, `max_knowledge_bytes`.
- **Done when:** endpoints behave per spec with workflows stubbed to enqueue only.
- **Tests:** integration per endpoint; access-model unit tests.

### M7-T02 · `RetrievalStore` port, pgvector adapter, conformance suite and retrieval core
- **Depends on:** M7-T01
- **Areas:** `ar_domain/knowledge/{store.py,store_types.py,store_pgvector.py,retrieval.py,acl.py}`, `libs/ar_domain/tests/conformance/retrieval_store/`, `ar_testing/fixtures/retrieval_store.py`, `ar_mcp_gateway/builtins/knowledge.py`, `ar_runtime/activities/auto_retrieve_knowledge.py`, `ar_api/routers/knowledge.py` (search), `.importlinter` (adapter isolation contract)
- **Spec:** [spec 10 §6–7, §10](../03-specs/10-knowledge.md#6-retrieval-store-port-retrievalstore), [schema §8 `chunk_embeddings`](../04-data/schema.md#8-knowledge-ar_domainknowledge), [request-flows §4](../02-architecture/request-flows.md#4-knowledge-grounded-answer-rag), [ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md)
- **Do:** Port and types exactly as spec 10 §6.1–6.3; factory `get_retrieval_store()` driven by `knowledge_collections.store_backend` and `AR_VECTOR_BACKEND` (only `pgvector` registered in this task; `qdrant` raises `StoreError("adapter not installed")`); pgvector adapter (spec 10 §7): supported-dims validation, `upsert`/`delete`/`set_acl` joining the caller's session, `build_hybrid_sql()` (HNSW dense branch with `hnsw.iterative_scan`, `tsvector` lexical branch, RRF, in-query tenant/version/ACL/classification predicates), optional `AR_VECTOR_PG_READ_DSN`, `export`, `health`; conformance suite C01–C16 parametrised by `retrieval_store` (pgvector param only for now); backend-independent retrieval pipeline (spec 10 §6.4): rerank via `/v1/rerank` (`AR_KNOWLEDGE_RERANK_CANDIDATES`), late ACL verification for `sensitivity='high'`, answerability; `knowledge.search`, `knowledge.get_document`, `knowledge.list_collections`, `auto_retrieve_knowledge` activity, `POST /api/v1/knowledge/search` (playground, `debug.backend`); metrics `ar_retrieval_store_*`.
- **Done when:** conformance suite passes for pgvector in `python-integration`; the SQL builder cannot produce a query without tenant, ACL and classification predicates in both branches (unit-tested exhaustively); `EXPLAIN` of the dense branch uses `ix_chunk_emb_hnsw_1024` (asserted in an integration test); retrieval returns citation metadata.
- **Tests:** unit (SQL builder, RRF, answerability); conformance C01–C16 (pgvector); integration leak test through the API (spec 10 §14).

### M7-T03 · Ingestion pipeline
- **Depends on:** M7-T02
- **Areas:** `services/ingest/src/ar_ingest/{workflows/ingest_document.py,activities/{fetch.py,parse.py,chunk.py,contextualise.py,embed.py,index.py}}`, `images/ingest/Dockerfile`
- **Spec:** [spec 10 §4.2](../03-specs/10-knowledge.md#42-ingestdocumentworkflowdocument_id-id-ingest-document_id), [request-flows §5](../02-architecture/request-flows.md#5-document-ingestion)
- **Do:** `IngestDocumentWorkflow`: fetch raw → `files(kind='knowledge_raw')`, Docling parse to Markdown (`knowledge_parsed`), structure-aware chunking (token sizes via tiktoken), contextual prefix generation (purpose `ingest_context`, alias `fast`, optional per collection), embeddings batch 64 (purpose `ingest_embed`), `index` activity writing `document_chunks` and `RetrievalStore.upsert` (`IndexedChunk` with acl, classification, source, title, modified_at, `lexical_text`) in one transaction for the pgvector adapter, status transitions, `knowledge.ingestion_completed`; upload source end-to-end; `AR_INGEST_MAX_BYTES`; non-retryable error classes.
- **Done when:** PDF, DOCX, PPTX, XLSX, HTML and Markdown fixtures ingest successfully; re-ingesting an unchanged document is a no-op (content hash).
- **Tests:** Temporal tests per activity failure; golden chunking snapshots for fixtures under `services/ingest/tests/fixtures/`.

### M7-T04 · Source sync framework, web and S3 connectors
- **Depends on:** M7-T03, M4-T08
- **Areas:** `ar_ingest/{workflows/source_sync.py,connectors/{base.py,upload.py,web.py,s3.py,database.py,mcp_resource.py}}`
- **Spec:** [spec 10 §4.1, §5](../03-specs/10-knowledge.md#41-sourcesyncworkflowsource_id-mode-job_id-id-sync-source_id), [connector-sdk §2](../05-contracts/connector-sdk.md#2-knowledge-connector-helper)
- **Do:** `SourceSyncWorkflow` (Temporal Schedule per source, cursor persistence, child `IngestDocumentWorkflow` with concurrency `AR_INGEST_SYNC_CONCURRENCY`, tombstones → `DeleteDocumentWorkflow`, `ingestion_jobs` stats); connectors `web` (robots, ETag, allowlist via proxy), `s3`, `database`, `mcp_resource`; credentials via secrets.
- **Done when:** a second sync with no changes fetches nothing; deleted objects are removed.
- **Tests:** integration (SeaweedFS for S3, local HTTP site for web); Temporal sync tests.

### M7-T05 · SharePoint, Confluence and Google Drive connectors with ACL sync
- **Depends on:** M7-T04
- **Areas:** `ar_ingest/connectors/{sharepoint.py,confluence.py,google_drive.py}`, `ar_ingest/workflows/acl_sync.py`, `ar_domain/knowledge/principals.py`
- **Spec:** [spec 10 §4.3, §5.2–5.3](../03-specs/10-knowledge.md#52-built-in-connectors)
- **Do:** Delta/change APIs per connector; external principal mapping (spec 10 §5.3) with unmapped principals dropped (logged); `AclSyncWorkflow` calling `RetrievalStore.set_acl` without re-embedding; `check_access` for late verification.
- **Done when:** permission removal at the source is reflected after ACL sync without re-ingestion.
- **Tests:** contract tests with recorded API fixtures (respx) for each connector; ACL change test.

### M7-T06 · Reindex, delete, source operations
- **Depends on:** M7-T04
- **Areas:** `ar_ingest/workflows/{reindex_collection.py,delete_document.py}`, `ar_api/routers/knowledge.py`
- **Spec:** [spec 10 §3, §4.4–4.5](../03-specs/10-knowledge.md#44-deletedocumentworkflowdocument_id-id-del-doc-document_id)
- **Do:** `POST /api/v1/knowledge/collections/{collection_id}:reindex` (blue/green by `index_version` per spec 10 §4.5; `target_backend` parameter accepted but only `pgvector` until M7-T09), `POST /api/v1/knowledge/documents/{document_id}:reingest`, `POST /api/v1/knowledge/sources/{source_id}:test`, `:sync`, `:pause`, `:resume`, `POST /api/v1/knowledge/jobs/{job_id}:cancel`; `DeleteDocumentWorkflow` (`RetrievalStore.delete`, chunks, files); `document.deleted` event.
- **Done when:** reindex with a new embedding model serves old results until the swap completes.
- **Tests:** Temporal tests; integration for each endpoint.

### M7-T07 · Citations in the runtime
- **Depends on:** M7-T02
- **Areas:** `ar_runtime/citations.py`, `ar_runtime/activities/finalize_run.py`, `ar_runtime/prompts/citations.md`
- **Spec:** [spec 07 §4](../03-specs/07-agent-runtime.md#4-context-assembly), [stream-events](../05-contracts/stream-events.md)
- **Do:** Citation index allocation per run (knowledge hits and tool results with URLs), prompt guidance to cite `[n]`, `citation.added` events, citation content parts stored on the final message, validation that cited indices exist (unknown indices stripped).
- **Done when:** final messages contain only valid citations and the UI can resolve each to a document/chunk the user can read.
- **Tests:** unit (index allocation, stripping); Temporal scripted run.

### M7-T08 · Web: knowledge pages and citations UI
- **Depends on:** M7-T05, M7-T06, M7-T07
- **Areas:** `apps/web/src/app/(app)/knowledge/**`, `apps/web/src/components/chat/Citations/**`
- **Spec:** [spec 19 `/knowledge`](../03-specs/19-web-app.md)
- **Do:** Collections grid, collection detail (documents table with status, upload dropzone, sources tab, jobs tab, settings, access), source wizard per kind (forms generated from `/api/v1/schemas/KnowledgeCollection`), search playground with scores, chat citation chips and source preview drawer.
- **Done when:** M7 exit scenario is demonstrable in the UI.
- **Tests:** Vitest; Playwright upload → ask → citation opens preview; axe.

### M7-T09 · Optional Qdrant adapter
- **Depends on:** M7-T08
- **Priority:** optional backend; not part of the M7 exit criteria; required before M15-T07.
- **Areas:** `ar_domain/knowledge/store_qdrant.py`, `libs/ar_domain/pyproject.toml` (extra `qdrant` = `qdrant-client`, `fastembed`), `ar_ingest/workflows/retrieval_store_audit.py`, `ar_testing/fixtures/retrieval_store.py` (`qdrant` param), `.github/workflows` job `conformance-qdrant`, `compose.yaml` profile `qdrant`, `images/ingest/Dockerfile` (pre-baked `Qdrant/bm25` in `AR_FASTEMBED_CACHE_DIR`)
- **Spec:** [spec 10 §8, §10](../03-specs/10-knowledge.md#8-qdrant-adapter-optional), [ci-cd](../07-ops/ci-cd.md), [local-dev §3](../07-ops/local-dev.md)
- **Do:** Adapter per spec 10 §8 (collection naming per tier, named dense + sparse BM25 vectors, payload indexes, filter builder with `should` blocks of 500 principals, adapter-side RRF identical to §6.3, `set_payload` ACL updates, scroll-based `export`, `/readyz` health); register in the factory; readiness check for `AR_QDRANT_URL`; `RetrievalStoreAuditWorkflow` + Schedule `retrieval-store-audit` (registered only when a qdrant collection exists); compose profile `qdrant`; CI job `conformance-qdrant` (PRs touching `store*`, nightly).
- **Done when:** conformance C01–C16 pass for the `qdrant` param; with `AR_VECTOR_BACKEND=qdrant` a new collection ingests and answers the M7 exit scenario identically (same documents cited).
- **Tests:** conformance (qdrant); unit (Qdrant filter builder); integration ingest → search with Qdrant container.

### M7-T10 · Migration between retrieval backends
- **Depends on:** M7-T09, M7-T06
- **Priority:** optional backend; not part of the M7 exit criteria; required before M15-T07.
- **Areas:** `ar_ingest/workflows/migrate_retrieval_store.py`, `ar_ingest/workflows/reindex_collection.py` (copy mode), `services/ingest/src/ar_ingest/cli.py`
- **Spec:** [spec 10 §9](../03-specs/10-knowledge.md#9-migrating-between-backends), [audit](../06-security/audit.md)
- **Do:** `MigrateRetrievalStoreWorkflow` and `ReindexCollectionWorkflow(..., target_backend)` copy mode (export → join metadata → upsert at new `index_version`, catch-up pass, count + parity verification, atomic switch, delayed source cleanup after `AR_VECTOR_MIGRATION_RETAIN_HOURS`, rollback); CLI `python -m ar_ingest.cli migrate-store` with `--dry-run` and `--rollback`; audit `collection.store_migrated`.
- **Done when:** a pgvector → qdrant → pgvector round trip on the M7 sample collections passes the parity check with zero downtime for `knowledge.search` (searches during the copy are served by the source).
- **Tests:** Temporal tests (copy, verification failure → no switch, rollback within window); round trip in `conformance-qdrant`.

# ADR-0009: Postgres + pgvector as the default retrieval store behind a `RetrievalStore` port; Qdrant as an optional adapter

- Status: Accepted (revised 2026-10-20; supersedes the original 2026-10-20 decision "Qdrant for knowledge retrieval; pgvector for memory and tool search")
- Date: 2026-10-20
- Decision log: [open-questions, Decision log](../../open-questions.md#decision-log)

## Context

The product is installed mostly in-house, one company per installation, or in a SaaS tier sized for hundreds of tenants rather than consumer scale. Typical knowledge sizes are 10^4–10^7 chunks per installation ([scaling](../../07-ops/scaling.md#4-retrieval-store-sizing)). Every additional stateful service raises operating cost for customer platform teams, backup/DR scope and the attack surface. Postgres is already mandatory, already enforces tenancy with RLS, and pgvector 0.8 provides HNSW indexes with iterative index scans that keep filtered queries accurate. Hybrid retrieval needs a lexical signal next to the dense one; Postgres full-text search (`tsvector`, `ts_rank_cd`) provides a BM25-style signal without a second engine.

Some large customers already run a dedicated vector database, or will exceed what one Postgres primary should serve (sustained > 50 knowledge queries/s on > 20 M chunks). The retrieval code therefore must not be welded to one engine.

## Decision

1. Retrieval goes through one port, `ar_domain.knowledge.store.RetrievalStore` ([spec 10 §6](../../03-specs/10-knowledge.md#6-retrieval-store-port-retrievalstore)): collection management, upsert, delete, ACL update, hybrid search with mandatory tenant/collection/version/ACL/classification filters, count, export (for migration), health. Domain code never imports an engine client.
2. **Default adapter: `pgvector`** ([spec 10 §7](../../03-specs/10-knowledge.md#7-pgvector-adapter-default)). Chunk vectors and lexical vectors live in the `chunk_embeddings` table ([schema §8](../../04-data/schema.md#8-knowledge-ar_domainknowledge)) under RLS; dense search uses per-dimension partial HNSW indexes on `halfvec`; lexical search uses a stored generated `tsvector` with a GIN index; fusion is RRF in SQL; ACL and classification filters run inside the same query.
3. **Optional adapter: `qdrant`** ([spec 10 §8](../../03-specs/10-knowledge.md#8-qdrant-adapter-optional)), selected with `AR_VECTOR_BACKEND=qdrant`. Not deployed by default: compose profile `qdrant`, Helm subchart `qdrant.enabled=false`.
4. The backend is recorded per collection (`knowledge_collections.store_backend`), so a migration between backends switches collection by collection with blue/green semantics ([spec 10 §9](../../03-specs/10-knowledge.md#9-migrating-between-backends)).
5. Every adapter must pass the shared conformance suite ([spec 10 §10](../../03-specs/10-knowledge.md#10-retrievalstore-conformance-suite)) in CI.
6. Memory facts and tool embeddings stay on pgvector directly (`vector(1024)`, HNSW, RLS); they are small, transactional and not behind the port.

## Consequences

- One fewer stateful service by default: backup, DR, NetworkPolicies, upgrades and security reviews cover Postgres only. Ingestion writes chunks and embeddings in the same transaction (no dual-write, no reconciliation).
- Tenant isolation for knowledge is enforced by RLS in addition to the adapter's explicit filter.
- Knowledge load shares the OLTP database. Mitigations: retrieval runs on a read replica when `AR_VECTOR_PG_READ_DSN` is set; `halfvec` halves index memory; the sizing guide sets the threshold at which operators move to the Qdrant adapter or to a dedicated Postgres cluster for retrieval ([scaling §4](../../07-ops/scaling.md#4-retrieval-store-sizing)).
- Postgres full-text ranking is BM25-style, not exact BM25 (no corpus-level IDF saturation). Retrieval-quality gates (recall@8 ≥ 0.85, MRR ≥ 0.6) are measured with the pgvector adapter ([eval-strategy](../../08-quality/eval-strategy.md)).
- Two adapters to maintain; the conformance suite and the narrow port keep this cost bounded.

## Alternatives considered

- **Qdrant as the default** (the original decision): best-in-class filtered HNSW and native sparse vectors, but adds a mandatory stateful service and a dual-write path for installations that rarely need it. Kept as an optional adapter.
- **OpenSearch**: heavier to operate for the same capability; no adapter planned.
- **ParadeDB / `pg_search` for true BM25**: extension not available on all managed Postgres offerings customers use; the port allows adding it later as a lexical strategy of the pgvector adapter.
